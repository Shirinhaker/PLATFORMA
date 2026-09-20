"""Yangi kod ro'yxatdan o'tish yozuvi bilan bir vaqtda amal qilishi kerak."""

from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.accounts.model import AccountType
from app.auth.model import AuthChallenge, PendingRegistration
from app.auth.security import derive_otp, sha256_token
from app.auth.service_parts import AuthService, base, login, registration
from app.core.config import Settings
from app.core.errors import ApiError


@pytest.fixture(params=[AccountType.USER, AccountType.BUSINESS])
def flow(fixed_now, monkeypatch, request):
    pending = PendingRegistration(
        id=7,
        account_type=request.param,
        payload_json={
            "account_type": request.param.value,
            "name": "Sinov",
            "direction": "Savdo",
            "address": "Sinov",
        },
        created_at=fixed_now,
        expires_at=fixed_now + timedelta(minutes=10),
    )
    challenge = AuthChallenge(
        id=8,
        purpose="register",
        pending_registration_id=7,
        start_expires_at=pending.expires_at,
        code_version=1,
        attempts=0,
        max_attempts=5,
    )
    session = SimpleNamespace(
        get=AsyncMock(return_value=pending),
        commit=AsyncMock(),
        rollback=AsyncMock(),
        add=lambda item: None,
    )

    @asynccontextmanager
    async def sessions():
        yield session

    settings = Settings(
        environment="test",
        otp_secret="test-otp-secret",
        csrf_secret="test-csrf-secret",
        outbox_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    )
    service = AuthService(sessions, SimpleNamespace(), settings)
    enqueue = AsyncMock()
    monkeypatch.setattr(base, "lock_challenge", AsyncMock(return_value=challenge))
    monkeypatch.setattr(login, "lock_challenge", AsyncMock(return_value=challenge))
    monkeypatch.setattr(
        registration, "find_challenge_by_start_token", AsyncMock(return_value=challenge)
    )
    monkeypatch.setattr(
        registration, "find_telegram_account", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        registration,
        "create_account",
        AsyncMock(return_value=SimpleNamespace(id=9, account_type=request.param)),
    )
    monkeypatch.setattr(
        registration, "create_session", AsyncMock(return_value=(None, "test-session"))
    )
    monkeypatch.setattr(base, "enqueue_event", enqueue)
    monkeypatch.setattr(registration, "enqueue_event", AsyncMock())
    monkeypatch.setattr(
        service, "_generate_unique_login", AsyncMock(return_value="u_test")
    )
    monkeypatch.setattr(service, "_cache_authenticated_session", AsyncMock())
    return service, challenge, pending, enqueue


@pytest.mark.parametrize("resend", [False, True])
async def test_fresh_registration_code_outlives_initial_link_deadline(
    flow, fixed_now, resend
):
    service, challenge, pending, _ = flow
    activated_at = fixed_now if resend else fixed_now + timedelta(minutes=9)
    await service.activate_deep_link("test-start", 42, activated_at)
    if resend:
        await service.resend_challenge(challenge.id, fixed_now + timedelta(minutes=9))
    verified_at = fixed_now + timedelta(minutes=11)
    code = derive_otp(challenge.id, challenge.code_version, "test-otp-secret")
    assert challenge.code_hash == sha256_token(code)
    assert challenge.code_expires_at > verified_at
    result = await service.verify_registration(challenge.id, code, "test", verified_at)
    assert result.account_type is pending.account_type
    assert pending.verified_at == verified_at
    assert pending.expires_at >= challenge.code_expires_at


async def test_resend_does_not_send_a_code_for_an_expired_registration(flow, fixed_now):
    service, challenge, _, enqueue = flow
    await service.activate_deep_link("test-start", 42, fixed_now)
    enqueue.reset_mock()
    with pytest.raises(ApiError) as error:
        await service.resend_challenge(challenge.id, fixed_now + timedelta(minutes=11))
    assert error.value.code == "invalid_code"
    enqueue.assert_not_awaited()


async def test_resend_keeps_old_code_invalid_and_new_code_single_use(flow, fixed_now):
    service, challenge, _, _ = flow
    await service.activate_deep_link("test-start", 42, fixed_now)
    old = derive_otp(challenge.id, 1, "test-otp-secret")
    now = fixed_now + timedelta(minutes=9)
    await service.resend_challenge(challenge.id, now)
    with pytest.raises(ApiError) as error:
        await service.verify_registration(challenge.id, old, "test", now)
    assert error.value.code == "invalid_code"
    fresh = derive_otp(challenge.id, 2, "test-otp-secret")
    await service.verify_registration(challenge.id, fresh, "test", now)
    with pytest.raises(ApiError):
        await service.verify_registration(challenge.id, fresh, "test", now)


async def test_code_expiry_is_not_extended_by_verification(flow, fixed_now):
    service, challenge, _, _ = flow
    await service.activate_deep_link("test-start", 42, fixed_now + timedelta(minutes=9))
    with pytest.raises(ApiError) as error:
        await service.verify_registration(
            challenge.id,
            derive_otp(challenge.id, 1, "test-otp-secret"),
            "test",
            fixed_now + timedelta(minutes=14),
        )
    assert error.value.code == "invalid_code"
