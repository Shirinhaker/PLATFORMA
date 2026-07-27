from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.outbox.model import OutboxEvent


async def enqueue_event(
    session: AsyncSession,
    topic: str,
    payload: dict[str, Any],
) -> int:
    now = datetime.now(UTC)
    event = OutboxEvent(
        topic=topic,
        payload=payload,
        status="pending",
        attempts=0,
        available_at=now,
        last_error="",
        created_at=now,
    )
    session.add(event)
    await session.flush()
    return event.id


async def claim_events(
    session: AsyncSession,
    worker_id: str,
    *,
    limit: int,
) -> list[OutboxEvent]:
    now = datetime.now(UTC)
    result = await session.execute(
        select(OutboxEvent)
        .where(
            OutboxEvent.status.in_(("pending", "retry")),
            OutboxEvent.available_at <= now,
        )
        .order_by(OutboxEvent.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    events = list(result.scalars())
    for event in events:
        event.status = "processing"
        event.locked_at = now
        event.locked_by = worker_id
        event.attempts += 1
    await session.flush()
    return events


async def mark_processed(
    session: AsyncSession,
    event_id: int,
    *,
    sanitized_payload: dict[str, Any] | None = None,
) -> None:
    event = await session.get(OutboxEvent, event_id, with_for_update=True)
    if event is None:
        raise LookupError(f"Outbox event topilmadi: {event_id}")
    if sanitized_payload is not None:
        event.payload = sanitized_payload
    event.status = "processed"
    event.processed_at = datetime.now(UTC)
    event.locked_at = None
    event.locked_by = None


async def mark_failed(
    session: AsyncSession,
    event_id: int,
    error: str,
) -> None:
    event = await session.get(OutboxEvent, event_id, with_for_update=True)
    if event is None:
        raise LookupError(f"Outbox event topilmadi: {event_id}")
    event.status = "failed" if event.attempts >= 5 else "retry"
    event.available_at = datetime.now(UTC) + timedelta(
        seconds=min(3600, 30 * (2 ** max(0, event.attempts - 1)))
    )
    event.last_error = error[:1000]
    event.locked_at = None
    event.locked_by = None
