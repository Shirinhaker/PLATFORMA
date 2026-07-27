import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import boto3
import fakeredis.aioredis
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.auth.service import AuthService
from app.core.config import Settings


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 7, 27, 8, 0, tzinfo=UTC)


@pytest.fixture
async def db_session():
    url = os.environ.get("KOPRIK_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("KOPRIK_TEST_DATABASE_URL required")
    engine = create_async_engine(url)
    connection = await engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()
        await engine.dispose()


@pytest.fixture
async def auth_service(db_session):
    @asynccontextmanager
    async def session_factory():
        yield db_session

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    settings = Settings(
        environment="test",
        telegram_bot_username="koprik_test_bot",
        otp_secret="test-otp-secret",
        csrf_secret="test-csrf-secret",
        outbox_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    )
    service = AuthService(session_factory, redis, settings)
    try:
        yield service
    finally:
        await redis.aclose()


@pytest.fixture
def s3_client():
    return boto3.client(
        "s3",
        endpoint_url="https://example.r2.cloudflarestorage.com",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="auto",
    )
