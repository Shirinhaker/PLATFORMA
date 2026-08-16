from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.account_settings.router import require_business_credentials_owner, router
from app.account_settings.schemas import BusinessCredentialsUpdate
from app.account_settings.service import AccountSettingsService
from app.accounts.model import Account, AccountType
from app.auth.dependencies import CurrentAccount
from app.auth.security import verify_password
from app.core.errors import ApiError
from app.db.base import Base
from app.profiles.model import ProfileLink

NOW = datetime(2026, 8, 11, 10, 0, tzinfo=UTC)


class AsyncStore:
    def __init__(self, sync: Session) -> None:
        self.sync = sync

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def flush(self):
        self.sync.flush()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


def account(identifier: int, account_type: AccountType, login: str) -> Account:
    return Account(
        id=identifier,
        account_type=account_type,
        login=login,
        password_hash="old-hash",
        telegram_user_id=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def settings_context():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(Account.__table__, ProfileLink.__table__),
    )
    with Session(engine) as seed:
        seed.add_all(
            (
                account(1, AccountType.BUSINESS, "turondokon"),
                account(2, AccountType.USER, "bandlogin"),
                ProfileLink(
                    user_account_id=2,
                    business_account_id=1,
                    created_at=NOW,
                ),
            )
        )
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    service = AccountSettingsService(sessions, now_provider=lambda: NOW)
    try:
        yield service, engine
    finally:
        engine.dispose()


async def test_business_owner_reads_and_updates_v1656_credentials(settings_context):
    service, engine = settings_context

    before = await service.get_business_credentials(
        account_id=2,
        account_type=AccountType.USER,
    )
    assert before.login == "turondokon"

    changed = await service.update_business_credentials(
        account_id=2,
        account_type=AccountType.USER,
        body=BusinessCredentialsUpdate(
            new_login="Yangi_Login",
            new_password="yangi-parol",
        ),
    )
    assert changed.login == "yangi_login"

    with Session(engine) as session:
        stored = session.get(Account, 1)
        assert stored is not None
        assert stored.login == "yangi_login"
        assert stored.password_hash != "yangi-parol"
        assert verify_password(stored.password_hash, "yangi-parol")


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (BusinessCredentialsUpdate(), "credentials_change_required"),
        (BusinessCredentialsUpdate(new_login="1bad"), "invalid_login"),
        (BusinessCredentialsUpdate(new_password="123"), "password_too_short"),
        (BusinessCredentialsUpdate(new_login="bandlogin"), "login_already_exists"),
    ],
)
async def test_v1656_credential_validation(settings_context, body, code):
    service, _engine = settings_context
    with pytest.raises(ApiError) as denied:
        await service.update_business_credentials(
            account_id=1,
            account_type=AccountType.BUSINESS,
            body=body,
        )
    assert denied.value.code == code


def test_account_settings_routes_are_typed_and_versioned():
    routes = {
        (route.path, method)
        for route in router.routes
        for method in route.methods or set()
    }
    expected = "/api/v1/account-settings/business-credentials"
    assert (expected, "GET") in routes
    assert (expected, "PUT") in routes


async def test_unlinked_user_and_staff_cannot_manage_business_credentials(
    settings_context,
):
    service, engine = settings_context
    with Session(engine) as seed:
        seed.add(account(3, AccountType.USER, "oddiyuser"))
        seed.commit()

    with pytest.raises(ApiError) as unlinked:
        await service.get_business_credentials(
            account_id=3,
            account_type=AccountType.USER,
        )
    assert unlinked.value.code == "linked_business_required"

    with pytest.raises(ApiError) as staff:
        require_business_credentials_owner(
            CurrentAccount(
                account_id=1,
                account_type=AccountType.BUSINESS,
                session_token="staff-session",
                actor_type="staff",
                staff_id=9,
            )
        )
    assert staff.value.code == "business_owner_required"
