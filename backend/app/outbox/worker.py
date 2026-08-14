from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
import os
import signal
import socket
from typing import Any

import httpx
from sqlalchemy import and_, delete, func, or_, select

from app.admin.model import AdminAuthChallenge
from app.auth.model import AuthChallenge, AuthSession, PendingRegistration
from app.auth.security import decrypt_outbox_secret, derive_otp
from app.auth.telegram import TelegramClient
from app.core.config import Settings
from app.core.metrics import OUTBOX_OLDEST_AGE, OUTBOX_PENDING
from app.db.session import Database
from app.outbox.repository import (
    claim_events,
    mark_failed,
    mark_processed,
    renew_lease,
)
from app.outbox.model import OutboxEvent
from app.notifications.push_worker import (
    build_firebase_sender,
    process_push_batch,
)
from app.media.storage import build_r2_storage
from app.media.model import MediaUploadGrant
from app.stories.service import StoryService


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


async def send_admin_code(
    settings: Settings,
    database: Database,
    telegram: TelegramClient,
    payload: dict[str, Any],
) -> None:
    """Admin kodi bazada ham, navbatda ham saqlanmaydi — qayta hisoblanadi."""
    async with database.session() as session:
        challenge = await session.get(
            AdminAuthChallenge, int(payload["challenge_id"])
        )
        if (
            challenge is None
            or challenge.consumed_at is not None
            or challenge.expires_at <= datetime.now(UTC)
            or challenge.telegram_user_id != int(payload["chat_id"])
        ):
            return
        code = derive_otp(challenge.id, 0, settings.admin_otp_secret)
        await telegram.send_message(
            challenge.telegram_user_id,
            f"Koprik admin tasdiqlash kodi: {code}",
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


async def send_business_credentials(
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
                "🏪 Biznes kabinetingiz ochildi!\n\n"
                f"Biznes login: {credentials['login']}\n"
                f"Biznes parol: {credentials['password']}\n\n"
                "Bu login/parol bilan biznes kabinetingizga alohida "
                "kirishingiz mumkin. Saqlab qo'ying."
            ),
        )
    finally:
        credentials.clear()


def build_handlers(
    settings: Settings,
    database: Database,
    telegram: TelegramClient,
    story_service: StoryService | None = None,
) -> dict[str, Handler]:
    async def auth_code_handler(payload: dict[str, Any]) -> None:
        await send_auth_code(settings, database, telegram, payload)

    async def credentials_handler(payload: dict[str, Any]) -> None:
        await send_credentials(settings, telegram, payload)

    async def business_credentials_handler(payload: dict[str, Any]) -> None:
        await send_business_credentials(settings, telegram, payload)

    async def admin_code_handler(payload: dict[str, Any]) -> None:
        await send_admin_code(settings, database, telegram, payload)

    async def story_media_handler(payload: dict[str, Any]) -> None:
        if story_service is None:
            raise RuntimeError("story_service_not_configured")
        await story_service.process_pending(
            int(payload["story_id"]),
            int(payload["size_bytes"]),
        )

    async def media_delete_handler(payload: dict[str, Any]) -> None:
        if story_service is None:
            raise RuntimeError("media_cleanup_service_not_configured")
        await story_service.cleanup_object(str(payload["object_key"]))

    handlers: dict[str, Handler] = {
        "foundation.echo": foundation_echo,
        "telegram.auth_code.send": auth_code_handler,
        "telegram.credentials.send": credentials_handler,
        "telegram.business_credentials.send": business_credentials_handler,
        "telegram.admin_code.send": admin_code_handler,
    }
    if story_service is not None:
        handlers["story.media.process"] = story_media_handler
        handlers["media.object.delete"] = media_delete_handler
    return handlers


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
        lease_stop = asyncio.Event()
        lease_task = asyncio.create_task(
            _renew_event_lease(
                database,
                event.id,
                worker_id,
                lease_stop,
            )
        )
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
                    if event.topic in {
                        "telegram.credentials.send",
                        "telegram.business_credentials.send",
                    }:
                        sanitized_payload = {
                            "account_id": event.payload.get("account_id"),
                            "delivery": "telegram",
                        }
                    await mark_processed(
                        session,
                        event.id,
                        sanitized_payload=sanitized_payload,
                    )
        finally:
            lease_stop.set()
            await lease_task
    return len(events)


async def _renew_event_lease(
    database: Database,
    event_id: int,
    worker_id: str,
    stop: asyncio.Event,
) -> None:
    while True:
        try:
            await asyncio.wait_for(stop.wait(), timeout=60)
            return
        except TimeoutError:
            try:
                async with database.session() as session:
                    async with session.begin():
                        active = await renew_lease(session, event_id, worker_id)
            except Exception:
                # Connection uzilishi workerning asosiy handler natijasini
                # yashirmasin; lease timeout recovery xavfsizlik tarmog‘i.
                return
            if not active:
                return


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


async def cleanup_orphan_profile_uploads(
    database: Database,
    storage,
    now: datetime,
) -> None:
    cutoff = now - timedelta(hours=24)
    async with database.session() as session:
        grants = list((await session.scalars(
            select(MediaUploadGrant)
            .where(
                MediaUploadGrant.status == "pending",
                MediaUploadGrant.created_at < cutoff,
            )
            .order_by(MediaUploadGrant.id)
            .limit(100)
            .with_for_update(skip_locked=True)
        )).all())
        for grant in grants:
            try:
                await asyncio.to_thread(storage.delete_object, grant.object_key)
            except Exception:
                continue
            grant.status = "cleaned"
        await session.commit()


async def update_outbox_metrics(database: Database, now: datetime) -> None:
    async with database.session() as session:
        pending, oldest = (await session.execute(
            select(func.count(OutboxEvent.id), func.min(OutboxEvent.created_at))
            .where(OutboxEvent.status.in_(("pending", "retry", "processing")))
        )).one()
    OUTBOX_PENDING.set(int(pending or 0))
    if oldest is None:
        OUTBOX_OLDEST_AGE.set(0)
    else:
        aware = oldest if oldest.tzinfo is not None else oldest.replace(tzinfo=UTC)
        OUTBOX_OLDEST_AGE.set(max(0, (now - aware).total_seconds()))


async def run_worker(settings: Settings, *, once: bool = False) -> None:
    database = Database(
        settings.database_url,
        pool_size=settings.worker_db_pool_size,
        max_overflow=settings.worker_db_max_overflow,
        pool_timeout=settings.worker_db_pool_timeout_seconds,
    )
    await database.start()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    last_cleanup: datetime | None = None
    last_metrics: datetime | None = None
    try:
        push_sender = build_firebase_sender(settings)
        storage = build_r2_storage(settings)
        async with httpx.AsyncClient(timeout=10) as http:
            telegram = TelegramClient(settings.telegram_bot_token, http)
            story_service = StoryService(database.session, storage)
            handlers = build_handlers(
                settings,
                database,
                telegram,
                story_service,
            )
            while not stop.is_set():
                now = datetime.now(UTC)
                if (
                    last_cleanup is None
                    or now - last_cleanup >= timedelta(hours=1)
                ):
                    await cleanup_expired_auth(database, now)
                    await cleanup_orphan_profile_uploads(database, storage, now)
                    last_cleanup = now
                if last_metrics is None or now - last_metrics >= timedelta(seconds=15):
                    await update_outbox_metrics(database, now)
                    last_metrics = now
                count = await process_batch(
                    database,
                    worker_id,
                    handlers=handlers,
                )
                if push_sender is not None:
                    count += await process_push_batch(database, push_sender)
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
