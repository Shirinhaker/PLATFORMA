from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.auth.dependencies import CurrentAccount
from app.auth.security import decrypt_outbox_secret, verify_password
from app.business_opening.router import (
    require_business_opening_owner,
    router,
)
from app.business_opening.schemas import BusinessOpeningWrite
from app.business_opening.service import BusinessOpeningService
from app.core.config import Settings
from app.core.errors import ApiError
from app.db.base import Base
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile


NOW = datetime(2026, 8, 11, 11, 0, tzinfo=UTC)
OUTBOX_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


class AsyncStore:
    def __init__(self, sync: Session) -> None:
        self.sync = sync

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def get(self, model, identifier, **kwargs):
        return self.sync.get(model, identifier, **kwargs)

    def add(self, value):
        self.sync.add(value)

    async def flush(self):
        self.sync.flush()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


def user_account(identifier: int, login: str = "u_egasi") -> Account:
    return Account(
        id=identifier,
        account_type=AccountType.USER,
        login=login,
        password_hash="old-hash",
        telegram_user_id=998_901_234_567,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def opening_context(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            UserProfile.__table__,
            BusinessProfile.__table__,
            ProfileLink.__table__,
        ),
    )
    with Session(engine) as seed:
        seed.add(user_account(1))
        seed.add(UserProfile(account_id=1, name="Ali", phone="+998901234567"))
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    enqueued: list[tuple[str, dict]] = []

    async def capture_event(_session, topic, payload):
        enqueued.append((topic, payload))
        return 1

    async def create_sqlite_account(
        session,
        *,
        account_type,
        login,
        password_hash,
        telegram_user_id,
        now,
    ):
        value = Account(
            id=2,
            account_type=account_type,
            login=login,
            password_hash=password_hash,
            telegram_user_id=telegram_user_id,
            status="active",
            created_at=now,
            updated_at=now,
        )
        session.add(value)
        await session.flush()
        return value

    monkeypatch.setattr(
        "app.business_opening.service.enqueue_event",
        capture_event,
    )
    monkeypatch.setattr(
        "app.business_opening.service.create_account",
        create_sqlite_account,
    )
    settings = Settings(
        environment="test",
        outbox_encryption_key=OUTBOX_KEY,
    )
    service = BusinessOpeningService(
        sessions,
        settings,
        now_provider=lambda: NOW,
    )
    try:
        yield service, engine, enqueued
    finally:
        engine.dispose()


async def test_v1656_user_opens_linked_business_and_receives_credentials_once(
    opening_context,
):
    service, engine, enqueued = opening_context

    result = await service.open_business(
        account_id=1,
        account_type=AccountType.USER,
        body=BusinessOpeningWrite(
            name=" Turon do‘koni ",
            direction="Savdo",
            activity_type="Oziq-ovqat do'koni",
            phone=" +998 90 111 22 33 ",
            address=" Qumqo‘rg‘on ",
        ),
    )

    assert result.ok is True
    assert result.biz_login.startswith("b_")
    assert result.biz_password

    with Session(engine) as session:
        business = session.get(Account, result.business_account_id)
        profile = session.get(BusinessProfile, result.business_account_id)
        link = session.get(ProfileLink, 1)
        owner = session.get(UserProfile, 1)
        assert business is not None
        assert business.account_type is AccountType.BUSINESS
        assert business.telegram_user_id == 998_901_234_567
        assert verify_password(business.password_hash, result.biz_password)
        assert profile is not None
        assert profile.name == "Turon do‘koni"
        assert profile.direction == "Savdo"
        assert profile.activity_type == "Oziq-ovqat do'koni"
        assert profile.phone == "+998 90 111 22 33"
        assert profile.address == "Qumqo‘rg‘on"
        assert link is not None
        assert link.business_account_id == business.id
        assert owner is not None and owner.has_business is True

    assert len(enqueued) == 1
    topic, payload = enqueued[0]
    assert topic == "telegram.business_credentials.send"
    assert payload["account_id"] == result.business_account_id
    assert payload["chat_id"] == 998_901_234_567
    assert "biz_password" not in str(payload)
    assert decrypt_outbox_secret(
        payload["encrypted_credentials"],
        OUTBOX_KEY,
    ) == {
        "login": result.biz_login,
        "password": result.biz_password,
    }

    with pytest.raises(ApiError) as duplicate:
        await service.open_business(
            account_id=1,
            account_type=AccountType.USER,
            body=BusinessOpeningWrite(name="Ikkinchi biznes"),
        )
    assert duplicate.value.code == "business_already_exists"
    assert duplicate.value.status_code == 400


async def test_v1656_business_name_is_required(opening_context):
    service, _engine, _enqueued = opening_context
    with pytest.raises(ApiError) as required:
        await service.open_business(
            account_id=1,
            account_type=AccountType.USER,
            body=BusinessOpeningWrite(name="   "),
        )
    assert required.value.status_code == 400
    assert required.value.code == "business_name_required"
    assert required.value.message == "Biznes nomi kiritilishi shart."


async def test_v1656_business_opening_rejects_wrong_account_type(opening_context):
    service, _engine, _enqueued = opening_context
    with pytest.raises(ApiError) as denied:
        await service.open_business(
            account_id=9,
            account_type=AccountType.BUSINESS,
            body=BusinessOpeningWrite(name="Turon"),
        )
    assert denied.value.code == "user_account_required"


def test_business_opening_route_is_typed_versioned_and_owner_only():
    routes = {
        (route.path, method)
        for route in router.routes
        for method in route.methods or set()
    }
    assert ("/api/v1/business-opening", "POST") in routes

    with pytest.raises(ApiError) as staff:
        require_business_opening_owner(CurrentAccount(
            account_id=1,
            account_type=AccountType.USER,
            session_token="staff-token",
            actor_type="staff",
            staff_id=3,
        ))
    assert staff.value.code == "business_opening_owner_required"
