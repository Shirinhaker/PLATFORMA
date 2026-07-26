from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
import os
import signal
import socket
from typing import Any

import httpx
from sqlalchemy import and_, delete, or_

from app.auth.model import AuthChallenge, AuthSession, PendingRegistration
from app.auth.security import decrypt_outbox_secret, derive_otp
from app.auth.telegram import TelegramClient
from app.core.config import Settings
from app.db.session import Database
from app.outbox.repository import (
    claim_events,
    mark_failed,
    mark_processed,
)


Handler = Callable[[dict[str, Any]], Awaitable[None]]


async def foundation_echo(payload: dict[str, Any]) -> None:
    if payload.get("message") != "phase1":
        raise ValueError("Foundation echo payload noto‘g‘ri.")


async def send_auth_code(
    settings: Settings,
    database: Database,
    telegram: TelegramClient,
    payload: dict[str, Any],
) -> None:
    async with database.session() as session:
        challenge = await session.get(
            AuthChallenge,
            int(payload["challenge_id"]),
            with_for_update=True,
        )
        if (
            challenge is None
            or challenge.verified_at is not None
            or challenge.invalidated_at is not None
            or challenge.code_expires_at is None
            or challenge.code_expires_at <= datetime.now(UTC)
            or challenge.code_version != int(payload["code_version"])
            or challenge.telegram_user_id != int(payload["chat_id"])
        ):
            return
        code = derive_otp(
            challenge.id,
            challenge.code_version,
            settings.otp_secret,
        )
        await telegram.send_message(
            challenge.telegram_user_id,
            f"Koprik tasdiqlash kodi: {code}",
        )


async def send_credentials(
    settings: Settings,
    telegram: TelegramClient,
    payload: dict[str, Any],
) -> None:
    credentials = decrypt_outbox_secret(
        str(payload["encrypted_credentials"]),
        settings.outbox_encryption_key,
    )
    try:
        await telegram.send_message(
            int(payload["chat_id"]),
            (
                f"Koprik login: {credentials['login']}\n"
                f"Koprik parol: {credentials['password']}"
            ),
        )
    finally:
        credentials.clear()


def build_handlers(
    settings: Settings,
    database: Database,
    telegram: TelegramClient,
) -> dict[str, Handler]:
    async def auth_code_handler(payload: dict[str, Any]) -> None:
        await send_auth_code(settings, database, telegram, payload)

    async def credentials_handler(payload: dict[str, Any]) -> None:
        await send_credentials(settings, telegram, payload)

    return {
        "foundation.echo": foundation_echo,
        "telegram.auth_code.send": auth_code_handler,
        "telegram.credentials.send": credentials_handler,
    }


async def process_batch(
    database: Database,
    worker_id: str,
    *,
    handlers: dict[str, Handler] | None = None,
    limit: int = 50,
) -> int:
    active_handlers = (
        handlers
        if handlers is not None
        else {"foundation.echo": foundation_echo}
    )
    async with database.session() as session:
        async with session.begin():
            events = await claim_events(session, worker_id, limit=limit)
    for event in events:
        handler = active_handlers.get(event.topic)
        if handler is None:
            async with database.session() as session:
                async with session.begin():
                    await mark_failed(
                        session,
                        event.id,
                        f"Ro‘yxatdan o‘tmagan topic: {event.topic}",
                    )
            continue
        try:
            await handler(event.payload)
        except Exception:
            async with database.session() as session:
                async with session.begin():
                    error = (
                        "Telegram xabarni yuborib bo‘lmadi."
                        if event.topic.startswith("telegram.")
                        else "Outbox handler xatosi."
                    )
                    await mark_failed(session, event.id, error)
        else:
            async with database.session() as session:
                async with session.begin():
                    sanitized_payload = None
                    if event.topic == "telegram.credentials.send":
                        sanitized_payload = {
                            "account_id": event.payload.get("account_id"),
                            "delivery": "telegram",
                        }
                    await mark_processed(
                        session,
                        event.id,
                        sanitized_payload=sanitized_payload,
                    )
    return len(events)


async def cleanup_expired_auth(
    database: Database,
    now: datetime,
) -> None:
    challenge_cutoff = now - timedelta(days=7)
    session_cutoff = now - timedelta(days=30)
    async with database.session() as session:
        await session.execute(
            delete(PendingRegistration).where(
                PendingRegistration.verified_at.is_(None),
                PendingRegistration.expires_at < now,
            )
        )
        await session.execute(
            delete(AuthChallenge).where(
                AuthChallenge.created_at < challenge_cutoff,
                or_(
                    AuthChallenge.start_expires_at < now,
                    AuthChallenge.code_expires_at < now,
                    AuthChallenge.verified_at.is_not(None),
                    AuthChallenge.invalidated_at.is_not(None),
                ),
            )
        )
        await session.execute(
            delete(AuthSession).where(
                or_(
                    AuthSession.expires_at < session_cutoff,
                    and_(
                        AuthSession.revoked_at.is_not(None),
                        AuthSession.revoked_at < session_cutoff,
                    ),
                )
            )
        )
        await session.commit()


async def run_worker(settings: Settings, *, once: bool = False) -> None:
    database = Database(settings.database_url)
    await database.start()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    last_cleanup: datetime | None = None
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            telegram = TelegramClient(settings.telegram_bot_token, http)
            handlers = build_handlers(settings, database, telegram)
            while not stop.is_set():
                now = datetime.now(UTC)
                if (
                    last_cleanup is None
                    or now - last_cleanup >= timedelta(hours=1)
                ):
                    await cleanup_expired_auth(database, now)
                    last_cleanup = now
                count = await process_batch(
                    database,
                    worker_id,
                    handlers=handlers,
                )
                if once:
                    return
                if count == 0:
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=1)
                    except TimeoutError:
                        continue
    finally:
        await database.stop()


def main() -> None:
    settings = Settings()
    once = os.environ.get("KOPRIK_WORKER_ONCE") == "1"
    asyncio.run(run_worker(settings, once=once))


if __name__ == "__main__":
    main()
