from contextlib import asynccontextmanager
from datetime import datetime

import fakeredis.aioredis
import pytest

from app.accounts.model import Account, AccountType
from app.auth.model import AuthChallenge
from app.auth.security import hash_password
from app.auth.shared_login import SharedLoginAuthService
from app.core.config import Settings
from app.core.errors import ApiError


async def _service(db_session):
    @asynccontextmanager
    async def session_factory():
        yield db_session

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = SharedLoginAuthService(
        session_factory,
        redis,
        Settings(
            environment="test",
            telegram_bot_username="koprik_test_bot",
            otp_secret="test-otp-secret",
            csrf_secret="test-csrf-secret",
            outbox_encryption_key=(
                "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
            ),
        ),
    )
    return service, redis


@pytest.mark.asyncio
async def test_same_login_can_select_user_or_business_account(
    db_session,
    fixed_now: datetime,
):
    password_hash = hash_password("Yaxshi-Parol-42")
    ordinary = Account(
        account_type=AccountType.USER,
        login="shared_owner",
        password_hash=password_hash,
        telegram_user_id=None,
        status="active",
        created_at=fixed_now,
        updated_at=fixed_now,
    )
    business = Account(
        account_type=AccountType.BUSINESS,
        login="shared_owner",
        password_hash=password_hash,
        telegram_user_id=None,
        status="active",
        created_at=fixed_now,
        updated_at=fixed_now,
    )
    db_session.add_all([ordinary, business])
    await db_session.commit()

    service, redis = await _service(db_session)
    try:
        with pytest.raises(ApiError) as captured:
            await service.start_login(
                " SHARED_OWNER ",
                "Yaxshi-Parol-42",
                fixed_now,
            )
        assert captured.value.code == "account_type_required"

        user_started = await service.start_login(
            "shared_owner",
            "Yaxshi-Parol-42",
            fixed_now,
            account_type=AccountType.USER,
        )
        business_started = await service.start_login(
            "shared_owner",
            "Yaxshi-Parol-42",
            fixed_now,
            account_type=AccountType.BUSINESS,
        )
    finally:
        await redis.aclose()

    user_challenge = await db_session.get(
        AuthChallenge,
        user_started.request_id,
    )
    business_challenge = await db_session.get(
        AuthChallenge,
        business_started.request_id,
    )
    assert user_challenge is not None
    assert business_challenge is not None
    assert user_challenge.account_id == ordinary.id
    assert business_challenge.account_id == business.id
    assert user_started.code_sent is False
    assert business_started.code_sent is False
