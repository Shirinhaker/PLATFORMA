from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.catalog.model import CatalogGroup, CatalogItem
from app.db.base import Base
from app.legacy_migration.model import OwnerState, ReviewState
from app.listings.model import Listing, ListingMedia
from app.profiles.model import BusinessProfile
from app.public_discovery.repository import build_public_id, load_public_profile
from app.public_discovery.schemas import PublicResultKind
from app.queues.model import QueueProvider, QueueProviderService


NOW = datetime(2026, 8, 1, tzinfo=UTC)


class AsyncStore:
    def __init__(self, session: Session):
        self.sync = session

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def get(self, model, key):
        return self.sync.get(model, key)


@pytest.mark.asyncio
async def test_public_business_profile_uses_live_catalog_and_listings():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            BusinessProfile.__table__,
            CatalogGroup.__table__,
            CatalogItem.__table__,
            QueueProvider.__table__,
            QueueProviderService.__table__,
            Listing.__table__,
            ListingMedia.__table__,
        ),
    )
    session = Session(engine, expire_on_commit=False)
    try:
        session.add_all((
            Account(
                id=41,
                account_type=AccountType.BUSINESS,
                login="turon",
                password_hash="hash",
                telegram_user_id=None,
                status="active",
                created_at=NOW,
                updated_at=NOW,
            ),
            BusinessProfile(
                account_id=41,
                name="Turon savdo",
                phone="+998901234567",
                description="Sifatli mahsulotlar",
                public_username="turonsavdo",
                direction="Savdo",
                activity_type="Do‘kon",
                address="Qumqo‘rg‘on",
                latitude=37.82,
                longitude=67.58,
                work_hours={},
                pay_card="",
                pay_holder="",
                pay_qr_object_key="",
                director="",
                tax_id="",
                logo_object_key="logos/turon.webp",
                logo_x=50,
                logo_y=50,
                logo_zoom=1,
                followers_count=17,
                following_count=2,
                rating_sum=0,
                rating_count=0,
                map_visible=True,
                dashboard_snapshot={},
                recent_activity=[],
                cabinet_payload={},
            ),
            CatalogGroup(
                id=51,
                business_account_id=41,
                source_record_key="group:1",
                owner_name_snapshot="Turon savdo",
                name="Oziq-ovqat",
                kind="product",
                status="active",
                review_state=ReviewState.READY,
                migration_run_id=None,
                created_at=NOW,
                updated_at=NOW,
            ),
            CatalogItem(
                id=61,
                business_account_id=41,
                source_record_key="item:1",
                catalog_group_id=51,
                owner_name_snapshot="Turon savdo",
                name="Non",
                price_text="4 000 so‘m",
                note="Issiq non",
                kind="product",
                queue_enabled=False,
                image_object_key="items/non.webp",
                status="active",
                owner_state=OwnerState.LINKED,
                review_state=ReviewState.READY,
                migration_run_id=None,
                created_at=NOW,
                updated_at=NOW,
            ),
            Listing(
                id=71,
                owner_user_account_id=None,
                owner_business_account_id=41,
                category="Savdo",
                title="Un sotiladi",
                price_text="Kelishiladi",
                description="50 kg",
                address="Qumqo‘rg‘on",
                latitude=None,
                longitude=None,
                visibility="all",
                status="active",
                review_state=ReviewState.READY,
                migration_run_id=1,
                created_at=NOW,
                updated_at=NOW,
            ),
            ListingMedia(
                id=81,
                listing_id=71,
                media_type="photo",
                object_key="listings/un.webp",
                position=0,
                migration_state="copied",
                migration_run_id=1,
            ),
        ))
        session.commit()
        public_id = build_public_id(PublicResultKind.BUSINESS, 41)

        profile = await load_public_profile(
            AsyncStore(session),
            kind="business",
            public_id=public_id,
            image_url_provider=lambda key: f"/media/{key}" if key else "",
        )

        assert profile is not None
        assert profile.name == "Turon savdo"
        assert profile.phone == "+998901234567"
        assert profile.items[0].name == "Non"
        assert profile.items[0].unit == "dona"
        assert profile.items[0].queue_enabled is False
        assert profile.items[0].group_name == "Oziq-ovqat"
        assert profile.items[0].image_url == "/media/items/non.webp"
        assert profile.listings[0].title == "Un sotiladi"
        assert profile.listings[0].image_url == "/media/listings/un.webp"
    finally:
        session.close()
        engine.dispose()
