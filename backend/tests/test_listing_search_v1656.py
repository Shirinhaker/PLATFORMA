from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.db.base import Base
from app.legacy_migration.model import ReviewState
from app.listings.model import Listing
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile
from app.public_discovery.repository import search_public_profiles
from app.public_discovery.schemas import PublicResultType, PublicSearchParams


NOW = datetime(2026, 8, 2, 11, 0, tzinfo=UTC)


class AsyncStore:
    def __init__(self, session: Session):
        self.sync = session

    async def execute(self, statement):
        return self.sync.execute(statement)


@pytest.fixture
def listing_search_store():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            UserProfile.__table__,
            BusinessProfile.__table__,
            ProfileLink.__table__,
            Listing.__table__,
        ),
    )
    session = Session(engine, expire_on_commit=False)
    session.add_all((
        Account(
            id=5,
            account_type=AccountType.USER,
            login="ali",
            password_hash="hash",
            telegram_user_id=None,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        ),
        UserProfile(
            account_id=5,
            name="Ali",
            phone="",
            public_username="ali",
            region="Surxondaryo viloyati",
            district="Qumqo‘rg‘on tumani",
            mahalla="",
            latitude=37.82,
            longitude=67.58,
            location_exact=True,
            avatar_object_key="",
            avatar_x=50,
            avatar_y=50,
            avatar_zoom=1,
            followers_count=0,
            following_count=0,
            has_business=False,
            dashboard_snapshot={},
            recent_activity=[],
            specialist_profile={},
            cabinet_payload={},
        ),
        Listing(
            id=31,
            owner_user_account_id=5,
            owner_business_account_id=None,
            source_record_key=None,
            category="moshina",
            title="Nexia 3 sotiladi",
            price_text="120 000 000 so'm",
            description="Yili 2024",
            address="Qumqo‘rg‘on",
            latitude=37.82,
            longitude=67.58,
            visibility="all",
            status="active",
            review_state=ReviewState.READY,
            migration_run_id=None,
            created_at=NOW,
            updated_at=NOW,
        ),
    ))
    session.commit()
    try:
        yield AsyncStore(session)
    finally:
        session.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_user_listing_is_returned_by_public_search(listing_search_store):
    result = await search_public_profiles(
        listing_search_store,
        PublicSearchParams(
            q="Nexia 3",
            result_type=PublicResultType.LISTING,
            district="Qumqo‘rg‘on tumani",
        ),
        include_content=False,
        include_listings=True,
    )

    assert result.total == 1
    assert result.items[0].kind.value == "listing"
    assert result.items[0].name == "Nexia 3 sotiladi"
    assert result.items[0].price_text == "120 000 000 so'm"
    assert result.items[0].owner_label == "Ali"
    assert result.items[0].public_id.startswith("l_")
    assert result.items[0].map_point is not None
    assert result.items[0].map_point.business_public_id.startswith("u_")
    assert result.items[0].map_point.latitude == 37.82
