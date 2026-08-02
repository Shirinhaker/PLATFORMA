from datetime import UTC, datetime
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.catalog.model import CatalogItem
from app.catalog.repository import build_content_public_id, get_public_catalog
from app.db.base import Base
from app.legacy_migration.model import OwnerState, ReviewState
from app.listings.model import Listing
from app.listings.repository import ListingRepository
from app.listings.service import ListingService
from app.orders.repository import OrderRepository
from app.profiles.model import BusinessProfile, UserProfile
from app.public_discovery.repository import (
    _resolve_public_profile_account_id,
    build_listing_public_id,
    build_public_id,
)
from app.public_discovery.schemas import PublicResultKind


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0010_public_id_indexed_lookup.py"
)
NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


class AsyncStore:
    def __init__(self, session: Session):
        self.sync = session

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def get(self, model, identity, **_kwargs):
        return self.sync.get(model, identity)

    async def rollback(self):
        self.sync.rollback()


def test_public_lookup_models_have_unique_public_id_indexes():
    expected = {
        UserProfile: "uq_user_profiles_public_id",
        BusinessProfile: "uq_business_profiles_public_id",
        CatalogItem: "uq_catalog_items_public_id",
        Listing: "uq_listings_public_id",
    }

    for model, index_name in expected.items():
        column = model.__table__.c.public_id
        assert column.type.length == 18
        assert column.nullable is True
        indexes = {index.name: index for index in model.__table__.indexes}
        assert indexes[index_name].unique is True
        assert tuple(indexes[index_name].columns) == (column,)


def test_public_id_migration_backfills_every_lookup_and_creates_indexes():
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "0010_public_id_indexed_lookup"' in source
    assert 'down_revision = "0009_orders_live_v1656"' in source
    for table in (
        "user_profiles",
        "business_profiles",
        "catalog_items",
        "listings",
    ):
        assert f'op.add_column(\n        "{table}"' in source
        assert f'"uq_{table}_public_id"' in source
    assert "batch_size=1000" in source
    assert "postgresql_concurrently=True" in source
    assert "notifications" not in source


def test_public_id_migration_preserves_existing_ids_byte_for_byte():
    spec = importlib.util.spec_from_file_location("public_id_migration", MIGRATION)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration._profile_public_id("user", 5) == build_public_id(
        PublicResultKind.USER,
        5,
    )
    assert migration._profile_public_id("business", 7) == build_public_id(
        PublicResultKind.BUSINESS,
        7,
    )
    assert migration._content_public_id("product", 11) == (
        build_content_public_id("product", 11)
    )
    assert migration._content_public_id("service", 12) == (
        build_content_public_id("service", 12)
    )
    assert migration._listing_public_id("", 21) == build_listing_public_id(21)


@pytest.mark.asyncio
async def test_order_repository_resolves_only_requested_indexed_public_ids():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            UserProfile.__table__,
            BusinessProfile.__table__,
            CatalogItem.__table__,
            Listing.__table__,
        ),
    )
    session = Session(engine, expire_on_commit=False)
    business_public_id = build_public_id(PublicResultKind.BUSINESS, 7)
    item_public_id = build_content_public_id("product", 11)
    listing_public_id = build_listing_public_id(21)
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
        BusinessProfile(
            account_id=7,
            public_id=business_public_id,
            name="Muhr",
            phone="",
        ),
        CatalogItem(
            id=11,
            public_id=item_public_id,
            business_account_id=7,
            source_record_key="11",
            catalog_group_id=None,
            owner_name_snapshot="Muhr",
            name="Non",
            price_text="4 000 so'm",
            unit="dona",
            note="",
            kind="product",
            queue_enabled=False,
            image_object_key="",
            status="active",
            owner_state=OwnerState.LINKED,
            review_state=ReviewState.READY,
            migration_run_id=None,
            created_at=NOW,
            updated_at=NOW,
        ),
        Listing(
            id=21,
            public_id=listing_public_id,
            owner_user_account_id=None,
            owner_business_account_id=7,
            source_record_key="21",
            category="uy",
            title="Uy sotiladi",
            price_text="",
            description="",
            address="",
            visibility="all",
            status="active",
            review_state=ReviewState.READY,
            migration_run_id=None,
            created_at=NOW,
            updated_at=NOW,
        ),
    ))
    session.commit()
    store = AsyncStore(session)
    repository = OrderRepository()

    try:
        profile = await repository.profile_by_public_id(
            store,
            kind="business",
            public_id=business_public_id,
        )
        items = await repository.catalog_items_by_public_ids(
            store,
            public_ids=[item_public_id],
        )
        listing = await repository.listing_by_public_id(
            store,
            public_id=listing_public_id,
        )

        assert profile is not None and profile.account_id == 7
        assert [item.id for item in items] == [11]
        assert listing is not None and listing.id == 21
    finally:
        session.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_public_profile_and_catalog_detail_filter_by_indexed_public_id():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            BusinessProfile.__table__,
            CatalogItem.__table__,
        ),
    )
    statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def record_statement(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(" ".join(statement.casefold().split()))

    session = Session(engine, expire_on_commit=False)
    business_public_id = build_public_id(PublicResultKind.BUSINESS, 7)
    item_public_id = build_content_public_id("product", 11)
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
        BusinessProfile(
            account_id=7,
            public_id=business_public_id,
            name="Muhr",
            phone="",
        ),
        CatalogItem(
            id=11,
            public_id=item_public_id,
            business_account_id=7,
            source_record_key="11",
            catalog_group_id=None,
            owner_name_snapshot="Muhr",
            name="Non",
            price_text="4 000 so'm",
            unit="dona",
            note="",
            kind="product",
            queue_enabled=False,
            image_object_key="",
            status="active",
            owner_state=OwnerState.LINKED,
            review_state=ReviewState.READY,
            migration_run_id=None,
            created_at=NOW,
            updated_at=NOW,
        ),
    ))
    session.commit()
    store = AsyncStore(session)

    try:
        statements.clear()
        account_id = await _resolve_public_profile_account_id(
            store,
            kind="business",
            public_id=business_public_id,
        )
        assert account_id == 7
        assert any(
            "business_profiles.public_id =" in statement
            for statement in statements
        )

        statements.clear()
        item = await get_public_catalog(store, item_public_id, lambda key: key)
        assert item is not None and item.public_id == item_public_id
        assert any(
            "catalog_items.public_id =" in statement
            for statement in statements
        )
    finally:
        session.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_listing_service_never_enumerates_all_listing_ids():
    target_public_id = build_listing_public_id(21)
    target = object()

    class IndexedListingRepository(ListingRepository):
        async def by_public_id(self, session, *, public_id):
            assert public_id == target_public_id
            return target

        async def all_ids(self, session):
            raise AssertionError("Barcha e'lon IDlarini yuklash taqiqlangan.")

    service = ListingService(
        lambda: None,
        lambda key: key,
        repository=IndexedListingRepository(),
    )

    resolved = await service._resolve(object(), target_public_id)

    assert resolved is target
