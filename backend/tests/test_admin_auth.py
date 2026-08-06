"""Admin sessiyasi va to'lov tasdiqlash huquqi.

Migratsiyagacha to'lovni tasdiqlash `require_business_owner` bilan
yopilgan edi, ya'ni **har qanday biznes egasi o'zining to'lovini o'zi
tasdiqlab** bepul obuna olishi mumkin edi. Bu testlar shu holatning
qaytishidan saqlaydi.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.admin.model import AdminAuthChallenge, AdminSession
from app.admin.service import AdminAuthService
from app.auth.security import derive_otp
from app.core.config import Settings
from app.core.errors import ApiError
from app.db.base import Base
from app.outbox.model import OutboxEvent


NOW = datetime(2026, 8, 6, 9, 0, tzinfo=UTC)
ADMIN_TG = 1423181561
OUTSIDER_TG = 555000111


class AsyncStore:
    def __init__(self, sync: Session) -> None:
        self.sync = sync
        self.sequences: dict[str, int] = {}

    def add(self, value):
        self.sync.add(value)

    def get_bind(self):
        return self.sync.get_bind()

    async def get(self, model, key, **kwargs):
        return self.sync.get(model, key)

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def flush(self):
        for value in list(self.sync.new):
            if not hasattr(value, "id") or value.id is not None:
                continue
            table = value.__table__.name
            highest = self.sequences.get(table)
            if highest is None:
                highest = int(
                    self.sync.scalar(select(func.max(value.__table__.c.id))) or 0
                )
            highest += 1
            self.sequences[table] = highest
            value.id = highest
        self.sync.flush()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


def _settings(admin_ids: str = str(ADMIN_TG)) -> Settings:
    return Settings(
        environment="test",
        telegram_bot_username="koprik_test_bot",
        otp_secret="test-otp-secret",
        csrf_secret="test-csrf-secret",
        outbox_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        admin_telegram_ids=admin_ids,
    )


@pytest.fixture
def admin_context():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            AdminAuthChallenge.__table__,
            AdminSession.__table__,
            OutboxEvent.__table__,
        ),
    )

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    def build(settings: Settings | None = None, now: datetime = NOW):
        return AdminAuthService(
            sessions,
            settings or _settings(),
            now_provider=lambda: now,
        )

    try:
        yield build, engine
    finally:
        engine.dispose()


def _code(challenge_id: int) -> str:
    return derive_otp(challenge_id, 0, "test-otp-secret")


# ------------------------------------------------------------------- ro'yxat


async def test_only_listed_telegram_id_gets_a_code(admin_context):
    build, engine = admin_context
    service = build()

    with pytest.raises(ApiError) as failure:
        await service.start(telegram_user_id=OUTSIDER_TG)
    assert failure.value.status_code == 403
    assert failure.value.code == "admin_not_allowed"

    # Ro'yxatda yo'q ID uchun kod umuman yaratilmaydi.
    with Session(engine) as check:
        assert check.scalar(
            select(func.count()).select_from(AdminAuthChallenge)
        ) == 0
        assert check.scalar(select(func.count()).select_from(OutboxEvent)) == 0


async def test_empty_allowlist_locks_everyone_out(admin_context):
    """Standart sozlamada hech kim admin emas."""
    build, _engine = admin_context
    service = build(_settings(admin_ids=""))

    with pytest.raises(ApiError) as failure:
        await service.start(telegram_user_id=ADMIN_TG)
    assert failure.value.status_code == 403


async def test_code_is_not_stored_in_the_queue(admin_context):
    build, engine = admin_context
    service = build()

    started = await service.start(telegram_user_id=ADMIN_TG)

    with Session(engine) as check:
        event = check.scalar(select(OutboxEvent))
        assert event.topic == "telegram.admin_code.send"
        # Navbatda faqat havola bor — kodning o'zi emas.
        assert set(event.payload) == {"challenge_id", "chat_id"}
        assert _code(started["challenge_id"]) not in str(event.payload)

        challenge = check.get(AdminAuthChallenge, started["challenge_id"])
        assert challenge.code_hash
        assert _code(started["challenge_id"]) not in challenge.code_hash


# --------------------------------------------------------------- tasdiqlash


async def test_valid_code_opens_a_session(admin_context):
    build, engine = admin_context
    service = build()
    started = await service.start(telegram_user_id=ADMIN_TG)

    token = await service.verify(
        challenge_id=started["challenge_id"],
        code=_code(started["challenge_id"]),
    )
    assert token
    assert await service.resolve(token) == ADMIN_TG

    with Session(engine) as check:
        # Raw token bazada saqlanmaydi.
        stored = check.scalar(select(AdminSession))
        assert token not in stored.token_hash
        assert len(stored.token_hash) == 64


async def test_wrong_code_counts_attempts_and_then_locks(admin_context):
    build, engine = admin_context
    service = build()
    started = await service.start(telegram_user_id=ADMIN_TG)

    for _ in range(5):
        with pytest.raises(ApiError) as failure:
            await service.verify(
                challenge_id=started["challenge_id"], code="000000"
            )
        assert failure.value.status_code == 400

    with pytest.raises(ApiError) as locked:
        await service.verify(
            challenge_id=started["challenge_id"],
            code=_code(started["challenge_id"]),
        )
    assert locked.value.status_code == 429
    with Session(engine) as check:
        assert check.scalar(select(func.count()).select_from(AdminSession)) == 0


async def test_code_works_once(admin_context):
    build, _engine = admin_context
    service = build()
    started = await service.start(telegram_user_id=ADMIN_TG)
    code = _code(started["challenge_id"])

    await service.verify(challenge_id=started["challenge_id"], code=code)
    with pytest.raises(ApiError) as failure:
        await service.verify(challenge_id=started["challenge_id"], code=code)
    assert failure.value.status_code == 409


async def test_expired_code_is_refused(admin_context):
    build, _engine = admin_context
    started = await build().start(telegram_user_id=ADMIN_TG)

    later = build(now=NOW + timedelta(minutes=6))
    with pytest.raises(ApiError) as failure:
        await later.verify(
            challenge_id=started["challenge_id"],
            code=_code(started["challenge_id"]),
        )
    assert failure.value.status_code == 410


# ------------------------------------------------------------------ sessiya


async def test_unknown_token_resolves_to_nobody(admin_context):
    build, _engine = admin_context
    service = build()
    assert await service.resolve("") is None
    assert await service.resolve("boshqa-token") is None


async def test_idle_session_is_revoked(admin_context):
    build, _engine = admin_context
    started = await build().start(telegram_user_id=ADMIN_TG)
    token = await build().verify(
        challenge_id=started["challenge_id"],
        code=_code(started["challenge_id"]),
    )

    idle = build(now=NOW + timedelta(minutes=31))
    assert await idle.resolve(token) is None
    # Bekor qilingan sessiya qaytib ochilmaydi.
    assert await build().resolve(token) is None


async def test_session_expires_after_ttl_even_when_active(admin_context):
    """Muntazam ishlatilsa ham 8 soatdan keyin sessiya yopiladi."""
    build, _engine = admin_context
    started = await build().start(telegram_user_id=ADMIN_TG)
    token = await build().verify(
        challenge_id=started["challenge_id"],
        code=_code(started["challenge_id"]),
    )

    # Har 20 daqiqada ishlatiladi — bo'sh turish qoidasi ishga tushmaydi.
    minutes = 20
    while minutes < 8 * 60:
        assert await build(now=NOW + timedelta(minutes=minutes)).resolve(
            token
        ) == ADMIN_TG
        minutes += 20

    expired = build(now=NOW + timedelta(hours=8, minutes=1))
    assert await expired.resolve(token) is None


async def test_removing_admin_from_list_kills_the_session(admin_context):
    """Ro'yxatdan chiqarilgan admin darhol quvviladi."""
    build, _engine = admin_context
    started = await build().start(telegram_user_id=ADMIN_TG)
    token = await build().verify(
        challenge_id=started["challenge_id"],
        code=_code(started["challenge_id"]),
    )
    assert await build().resolve(token) == ADMIN_TG

    without = AdminAuthService(
        build().__dict__["_session_factory"],
        _settings(admin_ids=""),
        now_provider=lambda: NOW,
    )
    assert await without.resolve(token) is None
    # Ro'yxatga qaytarilsa ham eski sessiya tiklanmaydi.
    assert await build().resolve(token) is None


async def test_logout_revokes_the_session(admin_context):
    build, _engine = admin_context
    service = build()
    started = await service.start(telegram_user_id=ADMIN_TG)
    token = await service.verify(
        challenge_id=started["challenge_id"],
        code=_code(started["challenge_id"]),
    )

    await service.logout(token)
    assert await service.resolve(token) is None
