import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.outbox.repository import (
    claim_events,
    enqueue_event,
    mark_processed,
    renew_lease,
)
from app.outbox.model import OutboxEvent


DATABASE_URL = os.environ.get("KOPRIK_TEST_DATABASE_URL", "")


@pytest.mark.skipif(not DATABASE_URL, reason="KOPRIK_TEST_DATABASE_URL required")
async def test_outbox_claim_is_durable_and_exclusive():
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions.begin() as session:
        event_id = await enqueue_event(
            session,
            "notification.telegram",
            {"user_id": 42, "text": "Sinov"},
        )
    async with sessions.begin() as session:
        claimed = await claim_events(session, "worker-a", limit=10)
        assert [event.id for event in claimed] == [event_id]
        await mark_processed(session, event_id)
    async with sessions.begin() as session:
        assert await claim_events(session, "worker-b", limit=10) == []
    await engine.dispose()


@pytest.mark.skipif(not DATABASE_URL, reason="KOPRIK_TEST_DATABASE_URL required")
async def test_outbox_reclaims_processing_event_after_lease_expires():
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    old_lock = datetime.now(UTC) - timedelta(minutes=10)
    async with sessions.begin() as session:
        event = OutboxEvent(
            topic="telegram.auth_code.send",
            payload={"challenge_id": 1, "chat_id": 2},
            status="processing",
            attempts=1,
            available_at=old_lock,
            locked_at=old_lock,
            locked_by="dead-worker",
            last_error="",
            created_at=old_lock,
            processed_at=None,
        )
        session.add(event)
        await session.flush()
        event_id = event.id
    async with sessions.begin() as session:
        claimed = await claim_events(
            session,
            "replacement-worker",
            limit=10,
            lease_timeout=timedelta(minutes=5),
        )
        assert [row.id for row in claimed] == [event_id]
        assert claimed[0].locked_by == "replacement-worker"
        assert claimed[0].attempts == 2
    await engine.dispose()


@pytest.mark.skipif(not DATABASE_URL, reason="KOPRIK_TEST_DATABASE_URL required")
async def test_outbox_does_not_steal_live_processing_lease():
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    async with sessions.begin() as session:
        session.add(OutboxEvent(
            topic="telegram.auth_code.send",
            payload={"challenge_id": 1, "chat_id": 2},
            status="processing",
            attempts=1,
            available_at=now,
            locked_at=now,
            locked_by="live-worker",
            last_error="",
            created_at=now,
            processed_at=None,
        ))
    async with sessions.begin() as session:
        claimed = await claim_events(
            session,
            "other-worker",
            limit=10,
            lease_timeout=timedelta(minutes=5),
        )
        assert claimed == []
    await engine.dispose()


@pytest.mark.skipif(not DATABASE_URL, reason="KOPRIK_TEST_DATABASE_URL required")
async def test_live_worker_can_heartbeat_its_processing_lease():
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    old_lock = datetime.now(UTC) - timedelta(minutes=4)
    async with sessions.begin() as session:
        event = OutboxEvent(
            topic="story.media.process",
            payload={"story_id": 1, "size_bytes": 1},
            status="processing",
            attempts=1,
            available_at=old_lock,
            locked_at=old_lock,
            locked_by="worker-a",
            last_error="",
            created_at=old_lock,
            processed_at=None,
        )
        session.add(event)
        await session.flush()
        event_id = event.id
    async with sessions.begin() as session:
        assert await renew_lease(session, event_id, "other-worker") is False
        assert await renew_lease(session, event_id, "worker-a") is True
    async with sessions() as session:
        refreshed = await session.get(OutboxEvent, event_id)
        assert refreshed.locked_at > old_lock
    await engine.dispose()
