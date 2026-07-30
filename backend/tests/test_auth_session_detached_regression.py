from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace

import fakeredis.aioredis

from app.accounts.model import AccountType
from app.auth import shared_login as shared_login_module
from app.auth.shared_login import SharedLoginAuthService
from app.core.config import Settings


async def test_session_resolution_does_not_read_rolled_back_orm_instance(
    fixed_now: datetime,
    monkeypatch,
):
    class RecordingSession:
        expired = False

        async def rollback(self):
            self.expired = True

        async def commit(self):
            pass

    session = RecordingSession()

    class RollbackExpiringAuthSession:
        expires_at = fixed_now + timedelta(days=1)

        @property
        def last_used_at(self):
            if session.expired:
                raise RuntimeError("detached auth session attribute access")
            return fixed_now

    auth_session = RollbackExpiringAuthSession()
    account = SimpleNamespace(
        id=42,
        account_type=AccountType.USER,
        login="u_detached_regression",
    )

    @asynccontextmanager
    async def session_factory():
        yield session

    async def resolve_from_database(db_session, raw_token, now):
        assert db_session is session
        assert raw_token == "raw-session-secret"
        return auth_session, account

    monkeypatch.setattr(
        shared_login_module,
        "resolve_stored_session",
        resolve_from_database,
    )

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = SharedLoginAuthService(
        session_factory,
        redis,
        Settings(
            environment="test",
            csrf_secret="test-csrf-secret",
        ),
    )
    try:
        identity = await service.resolve_session(
            "raw-session-secret",
            fixed_now + timedelta(minutes=1),
        )
    finally:
        await redis.aclose()

    assert identity is not None
    assert identity.login == "u_detached_regression"
