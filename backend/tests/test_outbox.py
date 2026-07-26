import os

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.outbox.repository import (
    claim_events,
    enqueue_event,
    mark_processed,
)


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
