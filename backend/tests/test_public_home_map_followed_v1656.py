from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.db.base import Base
from app.payments.model import (
    BusinessSubscription,
    PaymentMethod,
    PaymentRequest,
)
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile
from app.public_discovery.repository import build_public_id, load_public_home_map
from app.public_discovery.schemas import PublicFollowedProfile, PublicResultKind


NOW = datetime(2026, 8, 1, tzinfo=UTC)


class AsyncStore:
    def __init__(self, session: Session):
        self.sync = session

    async def scalars(self, statement):
        return self.sync.scalars(statement)


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
        name=f"Egasi {account_id}",
        phone="",
        public_username=f"owner{account_id}",
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


def business_profile(account_id: int, *, map_visible: bool) -> BusinessProfile:
    return BusinessProfile(
        account_id=account_id,
        name=f"Biznes {account_id}",
        phone="",
        description="",
        public_username=f"business{account_id}",
        direction="Savdo",
        activity_type="Do'kon",
        address="Qumqo'rg'on",
        latitude=37.8 + account_id / 1000,
        longitude=67.5 + account_id / 1000,
        work_hours={},
        pay_card="",
        pay_holder="",
        pay_qr_object_key="",
        director="",
        tax_id="",
        logo_object_key="",
        logo_x=50,
        logo_y=50,
        logo_zoom=1,
        followers_count=0,
        following_count=0,
        rating_sum=0,
        rating_count=0,
        map_visible=map_visible,
        dashboard_snapshot={},
        recent_activity=[],
        cabinet_payload={},
    )


@pytest.mark.asyncio
async def test_followed_businesses_ignore_map_visible_like_v1656(monkeypatch):
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
    session = Session(engine, expire_on_commit=False)
    try:
        for owner_id, business_id, map_visible in (
            (11, 21, True),
            (12, 22, False),
            (13, 23, False),
        ):
            session.add_all((
                account(owner_id, AccountType.USER),
                account(business_id, AccountType.BUSINESS),
                owner_profile(owner_id),
                business_profile(business_id, map_visible=map_visible),
                ProfileLink(
                    user_account_id=owner_id,
                    business_account_id=business_id,
                    created_at=NOW,
                ),
            ))
        session.commit()

        async def followed(*args, **kwargs):
            return [
                PublicFollowedProfile(
                    kind="business",
                    public_id=public_id,
                    name=name,
                )
                for public_id, name in (
                    (
                        build_public_id(PublicResultKind.BUSINESS, 21),
                        "Biznes 21",
                    ),
                    (
                        build_public_id(PublicResultKind.BUSINESS, 22),
                        "Biznes 22",
                    ),
                )
            ]

        monkeypatch.setattr(
            "app.public_discovery.repository.load_followed_profiles",
            followed,
        )
        async def no_native_pro(*args, **kwargs):
            return set()

        monkeypatch.setattr(
            "app.public_discovery.repository._active_pro_business_ids",
            no_native_pro,
        )
        payload = await load_public_home_map(
            AsyncStore(session),
            district="Qumqo'rg'on",
            image_url_provider=lambda value: value,
            account_id=7,
            account_type="user",
        )

        assert [item.name for item in payload.businesses] == [
            "Biznes 21",
            "Biznes 22",
        ]
    finally:
        session.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_native_demo_pro_keeps_real_business_visible_on_home_map():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            UserProfile.__table__,
            BusinessProfile.__table__,
            ProfileLink.__table__,
            PaymentMethod.__table__,
            PaymentRequest.__table__,
            BusinessSubscription.__table__,
        ),
    )
    session = Session(engine, expire_on_commit=False)
    try:
        session.add_all((
            account(11, AccountType.USER),
            account(21, AccountType.BUSINESS),
            owner_profile(11),
            business_profile(21, map_visible=True),
            ProfileLink(
                user_account_id=11,
                business_account_id=21,
                created_at=NOW,
            ),
            BusinessSubscription(
                id=301,
                business_account_id=21,
                legacy_source_id=None,
                plan_code="pro",
                duration_months=12,
                starts_at=int(NOW.timestamp()),
                expires_at=int(datetime(2030, 1, 1, tzinfo=UTC).timestamp()),
                status="active",
                # v1656 demo-activation haqiqiy biznes profilini demo qilmaydi.
                is_demo=True,
                payment_request_id=None,
                created_at=int(NOW.timestamp()),
            ),
        ))
        session.commit()

        payload = await load_public_home_map(
            AsyncStore(session),
            district="Qumqo‘rg‘on",
            image_url_provider=lambda value: value,
        )

        assert [item.name for item in payload.businesses] == ["Biznes 21"]
    finally:
        session.close()
        engine.dispose()
