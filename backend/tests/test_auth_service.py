import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace

import fakeredis.aioredis
import pytest
from sqlalchemy import func, select

from app.accounts.model import Account, AccountType
from app.auth import service as auth_service_module
from app.auth.model import AuthChallenge, AuthSession, PendingRegistration
from app.auth.schemas import Authenticated, RegistrationStart
from app.auth.security import (
    derive_otp,
    hash_password,
    sha256_token,
    verify_password,
)
from app.auth.service import AuthService
from app.core.config import Settings
from app.core.errors import ApiError
from app.outbox.model import OutboxEvent
from app.profiles.model import BusinessProfile, UserProfile


async def test_start_registration_stores_pending_form_and_hashes_start_token(
    fixed_now: datetime,
):
    class RecordingSession:
        def __init__(self):
            self.items = []
            self.commits = 0

        def add(self, item):
            self.items.append(item)

        async def flush(self):
            for index, item in enumerate(self.items, start=1):
                if hasattr(item, "id") and item.id is None:
                    item.id = index

        async def commit(self):
            self.commits += 1

        async def rollback(self):
            pass

    session = RecordingSession()

    @asynccontextmanager
    async def session_factory():
        yield session

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = AuthService(
        session_factory,
        redis,
        Settings(
            environment="test",
            telegram_bot_username="koprik_test_bot",
        ),
    )
    try:
        started = await service.start_registration(
            RegistrationStart(
                account_type=AccountType.USER,
                name="Test akkaunt",
            ),
            fixed_now,
        )
    finally:
        await redis.aclose()

    pending = next(
        item for item in session.items if isinstance(item, PendingRegistration)
    )
    challenge = next(
        item for item in session.items if isinstance(item, AuthChallenge)
    )
    raw_token = started.deep_link.rsplit("start=", 1)[1]
    assert pending.payload_json["name"] == "Test akkaunt"
    assert challenge.pending_registration_id == pending.id
    assert challenge.start_token_hash == sha256_token(raw_token)
    assert raw_token not in challenge.start_token_hash
    assert session.commits == 1


async def complete_registration(
    service: AuthService,
    *,
    account_type: AccountType,
    telegram_user_id: int,
    now: datetime,
) -> Authenticated:
    started = await service.start_registration(
        RegistrationStart(
            account_type=account_type,
            name="Test akkaunt",
            phone="+998901234567",
            direction="Savdo" if account_type is AccountType.BUSINESS else "",
            address="Termiz" if account_type is AccountType.BUSINESS else "",
        ),
        now,
    )
    await service.activate_deep_link(
        started.deep_link.rsplit("start=", 1)[1],
        telegram_user_id,
        now,
    )
    code = derive_otp(started.request_id, 1, "test-otp-secret")
    return await service.verify_registration(
        started.request_id,
        code,
        "pytest",
        now,
    )


async def seed_account(
    db_session,
    *,
    account_type: AccountType,
    login: str,
    telegram_user_id: int,
    now: datetime,
) -> Account:
    account = Account(
        account_type=account_type,
        login=login,
        password_hash=hash_password("Yaxshi-Parol-42"),
        telegram_user_id=telegram_user_id,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


async def test_same_telegram_can_register_one_user_and_one_business(
    auth_service: AuthService,
    fixed_now: datetime,
):
    ordinary = await complete_registration(
        auth_service,
        account_type=AccountType.USER,
        telegram_user_id=42,
        now=fixed_now,
    )
    business = await complete_registration(
        auth_service,
        account_type=AccountType.BUSINESS,
        telegram_user_id=42,
        now=fixed_now,
    )
    assert ordinary.account_id != business.account_id
    assert ordinary.account_type is AccountType.USER
    assert business.account_type is AccountType.BUSINESS


async def test_third_account_of_same_type_is_rejected(
    auth_service: AuthService,
    fixed_now: datetime,
):
    await complete_registration(
        auth_service,
        account_type=AccountType.USER,
        telegram_user_id=42,
        now=fixed_now,
    )

    with pytest.raises(ApiError) as captured:
        await complete_registration(
            auth_service,
            account_type=AccountType.USER,
            telegram_user_id=42,
            now=fixed_now,
        )

    assert captured.value.code == "telegram_account_type_exists"


async def test_login_finds_account_type_without_client_role(
    auth_service: AuthService,
    db_session,
    fixed_now: datetime,
):
    account = await seed_account(
        db_session,
        account_type=AccountType.BUSINESS,
        login="b_demo",
        telegram_user_id=42,
        now=fixed_now,
    )

    started = await auth_service.start_login(
        " B_DEMO ",
        "Yaxshi-Parol-42",
        fixed_now,
    )
    challenge = await db_session.get(AuthChallenge, started.request_id)

    assert challenge is not None
    assert challenge.account_id == account.id
    assert account.account_type is AccountType.BUSINESS
    assert started.code_sent is True


async def test_wrong_password_returns_invalid_credentials(
    auth_service: AuthService,
    db_session,
    fixed_now: datetime,
):
    await seed_account(
        db_session,
        account_type=AccountType.USER,
        login="u_demo",
        telegram_user_id=42,
        now=fixed_now,
    )

    with pytest.raises(ApiError) as captured:
        await auth_service.start_login("u_demo", "xato", fixed_now)

    assert captured.value.code == "invalid_credentials"


async def test_first_legacy_login_rehashes_and_second_login_uses_argon2(
    fixed_now: datetime,
    monkeypatch,
):
    class RecordingSession:
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0

        async def commit(self):
            self.commits += 1

        async def rollback(self):
            self.rollbacks += 1

    session = RecordingSession()

    @asynccontextmanager
    async def session_factory():
        yield session

    account = Account(
        id=77,
        account_type=AccountType.USER,
        login="u_legacy",
        password_hash=(
            "00112233445566778899aabbccddeeff$"
            "0ba712d93841d92cdc0a7a9149951429107b035040d07fd5bb3829bf79acd927"
        ),
        telegram_user_id=None,
        status="active",
        created_at=fixed_now,
        updated_at=fixed_now,
    )
    challenge_id = 0

    async def find_account(session_arg, login):
        assert session_arg is session
        assert login == "u_legacy"
        return account

    async def create_login_challenge(session_arg, **kwargs):
        nonlocal challenge_id
        assert session_arg is session
        challenge_id += 1
        return (
            SimpleNamespace(id=challenge_id, telegram_user_id=None),
            f"start-token-{challenge_id}",
        )

    monkeypatch.setattr(
        auth_service_module,
        "find_account_by_login",
        find_account,
    )
    monkeypatch.setattr(
        auth_service_module,
        "create_challenge",
        create_login_challenge,
    )
    service = AuthService(
        session_factory,
        redis=SimpleNamespace(),
        settings=Settings(environment="test"),
    )

    await service.start_login(
        "u_legacy",
        "koprik-test-password",
        fixed_now,
    )
    replacement = account.password_hash
    assert replacement.startswith("$argon2")
    assert verify_password(replacement, "koprik-test-password") is True

    await service.start_login(
        "u_legacy",
        "koprik-test-password",
        fixed_now,
    )
    assert account.password_hash == replacement
    assert session.commits == 2
    assert session.rollbacks == 0


async def test_old_code_is_invalid_after_resend(
    auth_service: AuthService,
    db_session,
    fixed_now: datetime,
):
    await seed_account(
        db_session,
        account_type=AccountType.USER,
        login="u_demo",
        telegram_user_id=42,
        now=fixed_now,
    )
    started = await auth_service.start_login(
        "u_demo",
        "Yaxshi-Parol-42",
        fixed_now,
    )
    old_code = derive_otp(started.request_id, 1, "test-otp-secret")
    resent_at = fixed_now + timedelta(seconds=60)
    resent = await auth_service.resend_challenge(started.request_id, resent_at)

    assert resent.code_version == 2
    with pytest.raises(ApiError) as captured:
        await auth_service.verify_login(
            started.request_id,
            old_code,
            "pytest",
            resent_at,
        )
    assert captured.value.code == "invalid_code"

    new_code = derive_otp(started.request_id, 2, "test-otp-secret")
    authenticated = await auth_service.verify_login(
        started.request_id,
        new_code,
        "pytest",
        resent_at,
    )
    assert authenticated.account_type is AccountType.USER


async def test_code_locks_after_five_wrong_attempts(
    auth_service: AuthService,
    db_session,
    fixed_now: datetime,
):
    await seed_account(
        db_session,
        account_type=AccountType.USER,
        login="u_demo",
        telegram_user_id=42,
        now=fixed_now,
    )
    started = await auth_service.start_login(
        "u_demo",
        "Yaxshi-Parol-42",
        fixed_now,
    )
    correct = derive_otp(started.request_id, 1, "test-otp-secret")
    wrong_codes = [
        value
        for value in (f"{number:06d}" for number in range(10))
        if value != correct
    ][:5]

    for index, wrong_code in enumerate(wrong_codes, start=1):
        with pytest.raises(ApiError) as captured:
            await auth_service.verify_login(
                started.request_id,
                wrong_code,
                "pytest",
                fixed_now,
            )
        expected = "challenge_locked" if index == 5 else "invalid_code"
        assert captured.value.code == expected

    with pytest.raises(ApiError) as captured:
        await auth_service.verify_login(
            started.request_id,
            correct,
            "pytest",
            fixed_now,
        )
    assert captured.value.code == "challenge_locked"


async def test_registration_is_atomic(
    auth_service: AuthService,
    db_session,
    fixed_now: datetime,
    monkeypatch,
):
    started = await auth_service.start_registration(
        RegistrationStart(
            account_type=AccountType.USER,
            name="Atomik test",
            phone="+998901234567",
        ),
        fixed_now,
    )
    await auth_service.activate_deep_link(
        started.deep_link.rsplit("start=", 1)[1],
        42,
        fixed_now,
    )

    async def broken_enqueue(*args, **kwargs):
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(auth_service_module, "enqueue_event", broken_enqueue)
    code = derive_otp(started.request_id, 1, "test-otp-secret")

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        await auth_service.verify_registration(
            started.request_id,
            code,
            "pytest",
            fixed_now,
        )

    for model in (Account, UserProfile, BusinessProfile, AuthSession):
        count = await db_session.scalar(select(func.count()).select_from(model))
        assert count == 0


async def test_credentials_outbox_contains_only_encrypted_secret(
    auth_service: AuthService,
    db_session,
    fixed_now: datetime,
):
    authenticated = await complete_registration(
        auth_service,
        account_type=AccountType.USER,
        telegram_user_id=42,
        now=fixed_now,
    )
    event = (
        await db_session.execute(
            select(OutboxEvent).where(
                OutboxEvent.topic == "telegram.credentials.send"
            )
        )
    ).scalar_one()

    assert set(event.payload) == {
        "account_id",
        "chat_id",
        "encrypted_credentials",
    }
    assert authenticated.login not in str(event.payload)
    assert authenticated.password not in str(event.payload)


async def test_session_last_used_at_is_throttled_to_five_minutes(
    auth_service: AuthService,
    db_session,
    fixed_now: datetime,
):
    authenticated = await complete_registration(
        auth_service,
        account_type=AccountType.USER,
        telegram_user_id=42,
        now=fixed_now,
    )
    stored = (
        await db_session.execute(
            select(AuthSession).where(
                AuthSession.account_id == authenticated.account_id
            )
        )
    ).scalar_one()

    identity = await auth_service.resolve_session(
        authenticated.session_token,
        fixed_now + timedelta(minutes=4),
    )
    await db_session.refresh(stored)
    assert identity is not None
    assert stored.last_used_at == fixed_now

    identity = await auth_service.resolve_session(
        authenticated.session_token,
        fixed_now + timedelta(minutes=6),
    )
    await db_session.refresh(stored)
    assert identity is not None
    assert stored.last_used_at == fixed_now + timedelta(minutes=6)


async def test_concurrent_session_resolution_is_coalesced_and_cached(
    fixed_now: datetime,
    monkeypatch,
):
    class RecordingSession:
        def __init__(self):
            self.rollbacks = 0

        async def rollback(self):
            self.rollbacks += 1

        async def commit(self):
            pass

    session = RecordingSession()

    @asynccontextmanager
    async def session_factory():
        yield session

    repository_calls = 0
    auth_session = SimpleNamespace(
        expires_at=fixed_now + timedelta(days=1),
        last_used_at=fixed_now,
    )
    account = SimpleNamespace(
        id=42,
        account_type=AccountType.USER,
        login="u_cached",
    )

    async def resolve_from_database(db_session, raw_token, now):
        nonlocal repository_calls
        assert db_session is session
        assert raw_token == "raw-session-secret"
        repository_calls += 1
        await asyncio.sleep(0.01)
        return auth_session, account

    monkeypatch.setattr(
        auth_service_module,
        "resolve_stored_session",
        resolve_from_database,
    )
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = AuthService(
        session_factory,
        redis,
        Settings(
            environment="test",
            csrf_secret="test-csrf-secret",
        ),
    )
    try:
        identities = await asyncio.gather(
            *(
                service.resolve_session("raw-session-secret", fixed_now)
                for _ in range(50)
            )
        )
        cached = await service.resolve_session(
            "raw-session-secret",
            fixed_now + timedelta(seconds=1),
        )
        keys = [key async for key in redis.scan_iter("auth:session:*")]
        values = [await redis.get(key) for key in keys]
    finally:
        await redis.aclose()

    assert repository_calls == 1
    assert session.rollbacks == 1
    assert all(identity is not None for identity in identities)
    assert cached is not None
    assert cached.login == "u_cached"
    assert keys
    assert all("raw-session-secret" not in key for key in keys)
    assert all("raw-session-secret" not in (value or "") for value in values)


async def test_cached_session_rechecks_database_after_touch_window(
    fixed_now: datetime,
    monkeypatch,
):
    class RecordingSession:
        async def rollback(self):
            pass

        async def commit(self):
            pass

    session = RecordingSession()

    @asynccontextmanager
    async def session_factory():
        yield session

    auth_session = SimpleNamespace(
        expires_at=fixed_now + timedelta(days=1),
        last_used_at=fixed_now,
    )
    account = SimpleNamespace(
        id=42,
        account_type=AccountType.USER,
        login="u_cached",
    )
    repository_calls = 0

    async def resolve_from_database(db_session, raw_token, now):
        nonlocal repository_calls
        repository_calls += 1
        return auth_session, account

    monkeypatch.setattr(
        auth_service_module,
        "resolve_stored_session",
        resolve_from_database,
    )
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = AuthService(
        session_factory,
        redis,
        Settings(
            environment="test",
            csrf_secret="test-csrf-secret",
        ),
    )
    try:
        first = await service.resolve_session(
            "raw-session-secret",
            fixed_now,
        )
        within_window = await service.resolve_session(
            "raw-session-secret",
            fixed_now + timedelta(minutes=4),
        )
        after_window = await service.resolve_session(
            "raw-session-secret",
            fixed_now + timedelta(minutes=6),
        )
    finally:
        await redis.aclose()

    assert first is not None
    assert within_window is not None
    assert after_window is not None
    assert repository_calls == 2
    assert auth_session.last_used_at == fixed_now + timedelta(minutes=6)


async def test_revoke_session_invalidates_cached_identity(
    fixed_now: datetime,
    monkeypatch,
):
    class RecordingSession:
        async def rollback(self):
            pass

        async def commit(self):
            pass

    session = RecordingSession()

    @asynccontextmanager
    async def session_factory():
        yield session

    auth_session = SimpleNamespace(
        expires_at=fixed_now + timedelta(days=1),
        last_used_at=fixed_now,
        revoked_at=None,
    )
    account = SimpleNamespace(
        id=42,
        account_type=AccountType.USER,
        login="u_cached",
    )
    repository_calls = 0

    async def resolve_from_database(db_session, raw_token, now):
        nonlocal repository_calls
        repository_calls += 1
        if auth_session.revoked_at is not None:
            return None
        return auth_session, account

    async def lock_stored_session(db_session, raw_token):
        return auth_session

    monkeypatch.setattr(
        auth_service_module,
        "resolve_stored_session",
        resolve_from_database,
    )
    monkeypatch.setattr(
        auth_service_module,
        "lock_session",
        lock_stored_session,
    )
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = AuthService(
        session_factory,
        redis,
        Settings(
            environment="test",
            csrf_secret="test-csrf-secret",
        ),
    )
    try:
        cached = await service.resolve_session(
            "raw-session-secret",
            fixed_now,
        )
        await service.revoke_session(
            "raw-session-secret",
            fixed_now + timedelta(seconds=1),
        )
        revoked = await service.resolve_session(
            "raw-session-secret",
            fixed_now + timedelta(seconds=2),
        )
    finally:
        await redis.aclose()

    assert cached is not None
    assert revoked is None
    assert repository_calls == 1
