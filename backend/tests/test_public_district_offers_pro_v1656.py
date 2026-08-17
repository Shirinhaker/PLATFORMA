from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.catalog.model import CatalogGroup, CatalogItem
from app.db.base import Base
from app.legacy_migration.model import (
    MigrationRun,
    OwnerState,
    ReviewState,
)
from app.payments.model import (
    BusinessSubscription,
    PaymentMethod,
    PaymentRequest,
)
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile
from app.public_discovery.queries.offers import load_public_district_offers
from app.public_discovery.queries.subscriptions import (
    _active_home_offer_business_ids,
)

NOW = datetime(2026, 8, 12, tzinfo=UTC)


class AsyncStore:
    def __init__(self, session: Session):
        self.sync = session

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)


class StatementCapture:
    def __init__(self):
        self.statement = None

    async def scalars(self, statement):
        self.statement = statement

        class EmptyRows:
            @staticmethod
            def all():
                return []

        return EmptyRows()


def account(account_id: int, account_type: AccountType) -> Account:
    return Account(
        id=account_id,
        account_type=account_type,
        login=f"account_{account_id}",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def owner_profile(account_id: int) -> UserProfile:
    return UserProfile(
        account_id=account_id,
        name="Egasi",
        phone="",
        public_username="egasi",
        region="Surxondaryo viloyati",
        district="Qumqo'rg'on tumani",
        mahalla="",
        latitude=None,
        longitude=None,
        location_exact=False,
        avatar_object_key="",
        avatar_x=50,
        avatar_y=50,
        avatar_zoom=1,
        followers_count=0,
        following_count=0,
        has_business=True,
        dashboard_snapshot={},
        recent_activity=[],
        specialist_profile={},
        cabinet_payload={},
    )


def business_profile(account_id: int) -> BusinessProfile:
    return BusinessProfile(
        account_id=account_id,
        name="Turon Savdo",
        phone="",
        description="",
        public_username="turon_savdo",
        direction="Savdo",
        activity_type="Do'kon",
        address="Qumqo'rg'on",
        latitude=37.8,
        longitude=67.5,
        work_hours={},
        pay_card="",
        pay_holder="",
        pay_qr_object_key="",
        director="",
        tax_id="",
        logo_object_key="logo.webp",
        logo_x=50,
        logo_y=50,
        logo_zoom=1,
        followers_count=0,
        following_count=0,
        rating_sum=0,
        rating_count=0,
        map_visible=True,
        dashboard_snapshot={},
        recent_activity=[],
        # Eski JSON bo'sh: test aynan yangi jadvalni tekshiradi.
        cabinet_payload={},
    )


@pytest.mark.asyncio
async def test_home_offer_filter_matches_v1656_plus_pro_policy_on_postgresql():
    session = StatementCapture()

    assert await _active_home_offer_business_ids(session, {21}) == set()
    assert session.statement is not None
    sql = str(
        session.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "business_subscriptions.plan_code IN ('plus', 'pro')" in sql
    assert "business_subscriptions.is_demo" not in sql


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("plan_code", "is_demo"),
    (("plus", True), ("pro", False)),
)
async def test_native_paid_subscription_shows_home_product_card(
    plan_code,
    is_demo,
):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            UserProfile.__table__,
            BusinessProfile.__table__,
            ProfileLink.__table__,
            MigrationRun.__table__,
            CatalogGroup.__table__,
            CatalogItem.__table__,
            PaymentMethod.__table__,
            PaymentRequest.__table__,
            BusinessSubscription.__table__,
        ),
    )
    session = Session(engine, expire_on_commit=False)
    try:
        session.add_all(
            (
                account(11, AccountType.USER),
                account(21, AccountType.BUSINESS),
                owner_profile(11),
                business_profile(21),
                ProfileLink(
                    user_account_id=11,
                    business_account_id=21,
                    created_at=NOW,
                ),
                CatalogItem(
                    id=101,
                    public_id="p_test",
                    business_account_id=21,
                    source_record_key=None,
                    catalog_group_id=None,
                    owner_name_snapshot="Turon Savdo",
                    name="Guruch",
                    price_text="18 000 so'm",
                    unit="kg",
                    note="",
                    kind="product",
                    queue_enabled=False,
                    image_object_key="guruch.webp",
                    status="active",
                    owner_state=OwnerState.LINKED,
                    review_state=ReviewState.READY,
                    migration_run_id=None,
                    created_at=NOW,
                    updated_at=NOW,
                ),
                BusinessSubscription(
                    id=301,
                    business_account_id=21,
                    legacy_source_id=None,
                    plan_code=plan_code,
                    duration_months=12,
                    starts_at=int(NOW.timestamp()),
                    expires_at=int(datetime(2030, 1, 1, tzinfo=UTC).timestamp()),
                    status="active",
                    is_demo=is_demo,
                    payment_request_id=None,
                    created_at=int(NOW.timestamp()),
                ),
            )
        )
        session.commit()

        payload = await load_public_district_offers(
            AsyncStore(session),
            district="Qumqo‘rg‘on",
            slot=0,
            image_url_provider=lambda key: f"/media/{key}",
        )

        assert payload.needs_district is False
        assert [item.title for item in payload.items] == ["Guruch"]
        assert payload.items[0].business_name == "Turon Savdo"
        assert payload.items[0].image == "/media/guruch.webp"
    finally:
        session.close()
        engine.dispose()
