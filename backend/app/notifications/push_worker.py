from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import or_, select, update

from app.core.config import Settings
from app.db.session import Database
from app.notifications.model import Notification, PushDevice, PushOutbox

RETRY_DELAYS = (60, 300, 900, 3600)
PERMANENT_FIREBASE_ERRORS = {
    "InvalidArgumentError",
    "SenderIdMismatchError",
    "UnregisteredError",
}


@dataclass(frozen=True)
class PendingPush:
    outbox_id: int
    device_id: int
    token: str
    title: str
    body: str
    attempts: int
    data: dict[str, str]


class PushSender(Protocol):
    async def send(self, push: PendingPush) -> str: ...


class FirebasePushSender:
    def __init__(self, app, messaging) -> None:
        self._app = app
        self._messaging = messaging

    async def send(self, push: PendingPush) -> str:
        message = self._messaging.Message(
            notification=self._messaging.Notification(
                title=push.title,
                body=push.body,
            ),
            data=push.data,
            token=push.token,
            android=self._messaging.AndroidConfig(priority="high"),
            apns=self._messaging.APNSConfig(headers={"apns-priority": "10"}),
        )
        return await asyncio.to_thread(
            self._messaging.send,
            message,
            app=self._app,
        )


def build_firebase_sender(settings: Settings) -> FirebasePushSender | None:
    raw = (
        settings.firebase_service_account_json
        or os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    ).strip()
    path = (
        settings.firebase_service_account_path
        or os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH", "")
    ).strip()
    if not raw and not path:
        return None

    import firebase_admin
    from firebase_admin import credentials, messaging

    try:
        app = firebase_admin.get_app()
    except ValueError:
        credential = credentials.Certificate(json.loads(raw) if raw else path)
        app = firebase_admin.initialize_app(credential)
    return FirebasePushSender(app, messaging)


def _push_data(notification: Notification) -> dict[str, str]:
    data = {
        "type": "notification",
        "notification_id": str(notification.id),
        "action_type": notification.action_type,
    }
    for name in (
        "order_id",
        "listing_id",
        "dining_order_id",
        "medical_queue_id",
        "ride_id",
    ):
        value = getattr(notification, name)
        if value is not None:
            data[name] = str(value)
    listing_public_id = str((notification.payload or {}).get("listing_public_id") or "")
    if listing_public_id:
        data["listing_public_id"] = listing_public_id
    return data


async def claim_pushes(
    session,
    *,
    now: int,
    limit: int = 50,
) -> list[PendingPush]:
    rows = (
        await session.execute(
            select(PushOutbox, Notification, PushDevice)
            .join(Notification, Notification.id == PushOutbox.notification_id)
            .join(PushDevice, PushDevice.id == PushOutbox.device_id)
            .where(
                or_(
                    PushOutbox.status == "pending",
                    (
                        (PushOutbox.status == "sending")
                        & (PushOutbox.last_attempt_at <= now - 300)
                    ),
                ),
                PushOutbox.attempts < 5,
                PushOutbox.available_at <= now,
                PushDevice.enabled.is_(True),
            )
            .order_by(PushOutbox.available_at, PushOutbox.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    claimed: list[PendingPush] = []
    for outbox, notification, device in rows:
        outbox.status = "sending"
        outbox.attempts += 1
        outbox.last_attempt_at = now
        claimed.append(
            PendingPush(
                outbox_id=int(outbox.id),
                device_id=int(device.id),
                token=device.token,
                title=notification.title,
                body=notification.body,
                attempts=int(outbox.attempts),
                data=_push_data(notification),
            )
        )
    return claimed


async def process_push_batch(
    database: Database,
    sender: PushSender,
    *,
    limit: int = 50,
    now: int | None = None,
) -> int:
    stamp = now if now is not None else int(datetime.now(UTC).timestamp())
    async with database.session() as session:
        pushes = await claim_pushes(session, now=stamp, limit=limit)
        await session.commit()

    for push in pushes:
        try:
            await sender.send(push)
        except Exception as error:
            error_name = type(error).__name__
            permanent = error_name in PERMANENT_FIREBASE_ERRORS or push.attempts >= 5
            delay = RETRY_DELAYS[min(push.attempts - 1, len(RETRY_DELAYS) - 1)]
            async with database.session() as session:
                await session.execute(
                    update(PushOutbox)
                    .where(PushOutbox.id == push.outbox_id)
                    .values(
                        status="failed" if permanent else "pending",
                        last_error=error_name[:160],
                        available_at=stamp + delay,
                    )
                )
                if permanent:
                    await session.execute(
                        update(PushDevice)
                        .where(PushDevice.id == push.device_id)
                        .values(enabled=False, updated_at=stamp)
                    )
                await session.commit()
        else:
            async with database.session() as session:
                await session.execute(
                    update(PushOutbox)
                    .where(PushOutbox.id == push.outbox_id)
                    .values(
                        status="sent",
                        sent_at=stamp,
                        last_error="",
                    )
                )
                await session.commit()
    return len(pushes)
