from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.core.config import Settings
from app.core.errors import ApiError
from app.db.base import Base
from app.legacy_migration.model import ReviewState
from app.listings.live_sync import sync_business_listings
from app.listings.model import Listing, ListingMedia, ListingSave
from app.listings.schemas import (
    ListingCreate,
    ListingMediaRead,
    ListingPatch,
    ListingRead,
)
from app.listings.service import ListingService
from app.main import create_app
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile


NOW = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)


class AsyncStore:
    def __init__(self, session: Session):
        self.sync = session
        self.sequences: dict[str, int] = {}

    def add(self, value):
        self.sync.add(value)

    async def delete(self, value):
        self.sync.delete(value)

    async def flush(self):
        for value in list(self.sync.new):
            if not hasattr(value, "id") or value.id is not None:
                continue
            table = value.__table__.name
            if table not in self.sequences:
                highest = self.sync.scalar(select(func.max(value.__table__.c.id)))
                self.sequences[table] = int(highest or 0)
            self.sequences[table] += 1
            value.id = self.sequences[table]
        self.sync.flush()

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def get(self, model, identity):
        return self.sync.get(model, identity)

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


@pytest.fixture
def listing_store():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            BusinessProfile.__table__,
            UserProfile.__table__,
            ProfileLink.__table__,
            Listing.__table__,
            ListingMedia.__table__,
            ListingSave.__table__,
        ),
    )
    session = Session(engine, expire_on_commit=False)
    session.add_all((
        Account(
            id=7,
            account_type=AccountType.BUSINESS,
            login="business_7",
            password_hash="hash",
            telegram_user_id=None,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        ),
        Account(
            id=5,
            account_type=AccountType.USER,
            login="user_5",
            password_hash="hash",
            telegram_user_id=None,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        ),
        BusinessProfile(
            account_id=7,
            name="Muhr",
            phone="",
            description="",
            public_username="muhr",
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
            logo_object_key="",
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
            cabinet_payload={},
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
        ProfileLink(
            user_account_id=5,
            business_account_id=7,
            created_at=NOW,
        ),
    ))
    session.commit()
    try:
        yield AsyncStore(session)
    finally:
        session.close()
        engine.dispose()


def test_live_listing_models_are_not_tied_to_a_migration_run():
    assert Listing.__table__.c.migration_run_id.nullable is True
    assert ListingMedia.__table__.c.migration_run_id.nullable is True
    assert Listing.__table__.c.source_record_key.nullable is True
    assert {
        "owner_user_account_id",
        "listing_id",
        "created_at",
    }.issubset(ListingSave.__table__.c.keys())


@pytest.mark.asyncio
async def test_business_cabinet_listing_is_live_synced_to_public_table(listing_store):
    payload = {
        "listings": [{
            "id": 11,
            "cat": "uy",
            "title": "3 xonali kvartira",
            "price": "Kelishilgan",
            "description": "Markazda",
            "address": "Qumqo‘rg‘on",
            "lat": 37.82,
            "lng": 67.58,
            "visibility": "all",
            "status": "active",
            "media": [{
                "type": "photo",
                "object_key": "private/business/7/listing_photo/a.webp",
            }],
        }],
    }

    await sync_business_listings(
        listing_store,
        account_id=7,
        payload=payload,
        changed_resources={"listings"},
    )

    row = (await listing_store.scalars(select(Listing))).one()
    assert row.owner_business_account_id == 7
    assert row.source_record_key == "11"
    assert row.title == "3 xonali kvartira"
    assert row.review_state is ReviewState.READY
    media = (await listing_store.scalars(select(ListingMedia))).one()
    assert media.object_key.endswith("a.webp")


@pytest.mark.asyncio
async def test_user_can_create_save_and_delete_listing_with_real_media(listing_store):
    @asynccontextmanager
    async def sessions():
        yield listing_store

    service = ListingService(sessions, lambda key: f"/media/{key}")
    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=ListingCreate(
            cat="moshina",
            title="Nexia 3 sotiladi",
            price="Kelishilgan",
            descr="Yili 2024",
            address="Qumqo‘rg‘on",
            lat=37.82,
            lng=67.58,
            visibility="own",
            media=[{
                "type": "photo",
                "object_key": "private/user/5/listing_photo/a.webp",
            }],
        ),
    )

    assert created.visibility == "all"
    assert created.media[0].url.endswith("listing_photo/a.webp")
    assert (await service.list_public(
        category="moshina",
        query="Nexia",
        current_account_id=5,
    ))[0].title == "Nexia 3 sotiladi"

    assert await service.toggle_save(
        public_id=created.public_id,
        account_id=5,
        account_type=AccountType.USER,
    ) is True
    assert (await service.list_saved(account_id=5))[0].is_saved is True
    assert await service.toggle_save(
        public_id=created.public_id,
        account_id=5,
        account_type=AccountType.USER,
    ) is False

    await service.delete(
        public_id=created.public_id,
        account_id=5,
        account_type=AccountType.USER,
    )
    assert await service.list_owner(account_id=5, account_type=AccountType.USER) == []


@pytest.mark.asyncio
async def test_review_required_listing_is_not_public_or_saveable(listing_store):
    @asynccontextmanager
    async def sessions():
        yield listing_store

    service = ListingService(sessions, lambda key: f"/media/{key}")
    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=ListingCreate(
            cat="uy",
            title="Tekshiruvdagi uy",
            price="",
            descr="",
            address="Qumqo‘rg‘on",
            lat=37.82,
            lng=67.58,
            visibility="all",
            media=[],
        ),
    )
    row = listing_store.sync.scalar(select(Listing))
    row.review_state = ReviewState.REVIEW_REQUIRED
    listing_store.sync.commit()

    assert await service.get_public(created.public_id) is None
    with pytest.raises(ApiError) as error:
        await service.toggle_save(
            public_id=created.public_id,
            account_id=5,
            account_type=AccountType.USER,
        )
    assert error.value.message == "E'lon topilmadi."


@pytest.mark.asyncio
async def test_business_mode_saves_to_its_linked_user_cabinet(listing_store):
    @asynccontextmanager
    async def sessions():
        yield listing_store

    service = ListingService(sessions, lambda key: f"/media/{key}")
    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=ListingCreate(
            cat="uy",
            title="Saqlanadigan uy",
            price="",
            descr="",
            address="Qumqo‘rg‘on",
            lat=37.82,
            lng=67.58,
            visibility="all",
            media=[],
        ),
    )

    assert await service.toggle_save(
        public_id=created.public_id,
        account_id=7,
        account_type=AccountType.BUSINESS,
    ) is True
    saved = (await listing_store.scalars(select(ListingSave))).one()
    assert saved.owner_user_account_id == 5
    rows = await service.list_public(
        category="uy",
        query="",
        current_account_id=7,
        current_account_type=AccountType.BUSINESS,
    )
    assert rows[0].is_saved is True


@pytest.mark.asyncio
async def test_owner_can_delete_an_inactive_listing(listing_store):
    @asynccontextmanager
    async def sessions():
        yield listing_store

    service = ListingService(sessions, lambda key: f"/media/{key}")
    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=ListingCreate(
            cat="uy",
            title="Vaqtincha yopiq e'lon",
            price="",
            descr="",
            address="Qumqo‘rg‘on",
            lat=37.82,
            lng=67.58,
            visibility="all",
            media=[],
        ),
    )
    updated = await service.patch(
        public_id=created.public_id,
        account_id=5,
        account_type=AccountType.USER,
        body=ListingPatch(status="inactive"),
    )
    assert updated.status == "inactive"

    await service.delete(
        public_id=created.public_id,
        account_id=5,
        account_type=AccountType.USER,
    )
    assert await service.list_owner(account_id=5, account_type=AccountType.USER) == []


class FakeListingService:
    def __init__(self):
        self.category = ""

    async def counts(self):
        return {"uy": 2, "ish": 1}

    async def list_public(
        self,
        *,
        category,
        query,
        current_account_id=None,
        current_account_type=None,
    ):
        self.category = category
        return [sample_listing()]

    async def get_public(
        self,
        public_id,
        *,
        current_account_id=None,
        current_account_type=None,
    ):
        return sample_listing(public_id)


def sample_listing(public_id: str = "l_1234567890abcdef") -> ListingRead:
    return ListingRead(
        public_id=public_id,
        cat="uy",
        title="3 xonali kvartira",
        price="Kelishilgan",
        descr="Markazda",
        address="Qumqo‘rg‘on",
        lat=37.82,
        lng=67.58,
        visibility="all",
        status="active",
        created_at=NOW,
        media=[ListingMediaRead(type="photo", url="/media/home.webp")],
        owner_kind="business",
        owner_public_id="b_1234567890abcdef",
        owner_name="Muhr",
        is_saved=False,
    )


def test_public_listing_counts_list_and_detail_match_v1656_contract():
    app = create_app(Settings(environment="test", listings_enabled=True))
    service = FakeListingService()
    app.state.listing_service = service
    client = TestClient(app)

    counts = client.get("/api/v1/public/listings/counts")
    listing = client.get("/api/v1/public/listings", params={"cat": "uy"})
    detail = client.get("/api/v1/public/listings/l_1234567890abcdef")

    assert counts.status_code == 200
    assert counts.json() == {"uy": 2, "ish": 1}
    assert listing.status_code == 200
    assert listing.json()[0]["title"] == "3 xonali kvartira"
    assert listing.json()[0]["media"][0]["type"] == "photo"
    assert service.category == "uy"
    assert detail.status_code == 200
    assert detail.json()["owner_public_id"].startswith("b_")
