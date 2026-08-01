from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.catalog.live_sync import sync_business_catalog
from app.catalog.model import CatalogGroup, CatalogItem
from app.db.base import Base
from app.legacy_migration.model import ReviewState
from app.profiles.model import BusinessProfile
from app.public_discovery.repository import search_public_profiles
from app.public_discovery.schemas import PublicSearchParams


NOW = datetime(2026, 8, 1, tzinfo=UTC)


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


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            BusinessProfile.__table__,
            CatalogGroup.__table__,
            CatalogItem.__table__,
        ),
    )
    session = Session(engine, expire_on_commit=False)
    try:
        yield AsyncStore(session)
    finally:
        session.close()
        engine.dispose()


def seed_business(store: AsyncStore, account_id: int, name: str) -> None:
    store.sync.add_all((
        Account(
            id=account_id,
            account_type=AccountType.BUSINESS,
            login=f"business_{account_id}",
            password_hash="hash",
            telegram_user_id=None,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        ),
        BusinessProfile(
            account_id=account_id,
            name=name,
            phone="",
            description="",
            public_username=f"business{account_id}",
            direction="Ta'lim faoliyati",
            activity_type="O'quv markazi",
            address="Qumqo'rg'on",
            latitude=None,
            longitude=None,
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
    ))
    store.sync.commit()


@pytest.mark.asyncio
async def test_live_items_are_immediately_searchable_with_monolith_fields(store):
    seed_business(store, 7, "Muhr")
    payload = {
        "item_groups": [],
        "items": [
            {"id": 1, "name": "ingliz tili", "price": 350000, "kind": "service"},
            {"id": 2, "name": "stomatolog", "price": "", "kind": "service"},
            {"id": 3, "name": "fsf", "price": ""},
        ],
    }

    await sync_business_catalog(
        store,
        account_id=7,
        owner_name="Muhr",
        payload=payload,
        changed_resources={"items"},
    )

    stomatolog = await search_public_profiles(
        store,
        PublicSearchParams(q="stomatolog", result_type="service"),
    )
    english = await search_public_profiles(
        store,
        PublicSearchParams(q="ingliz tili", result_type="service"),
    )
    fsf = await search_public_profiles(
        store,
        PublicSearchParams(q="fsf", result_type="product"),
    )

    assert [(item.name, item.kind.value) for item in stomatolog.items] == [
        ("stomatolog", "service")
    ]
    assert english.items[0].name == "ingliz tili"
    assert english.items[0].price_text == "350000"
    assert english.items[0].owner_label == "Muhr"
    assert [(item.name, item.kind.value) for item in fsf.items] == [
        ("fsf", "product")
    ]


@pytest.mark.asyncio
async def test_patch_and_delete_are_reflected_without_catalog_duplicates(store):
    seed_business(store, 7, "Muhr")
    payload = {
        "item_groups": [],
        "items": [{"id": 1, "name": "stomatolog", "kind": "service"}],
    }
    await sync_business_catalog(
        store,
        account_id=7,
        owner_name="Muhr",
        payload=payload,
        changed_resources={"items"},
    )

    payload["items"][0].update({"name": "Tish shifokori", "price": "120000"})
    await sync_business_catalog(
        store,
        account_id=7,
        owner_name="Muhr",
        payload=payload,
        changed_resources={"items"},
    )

    assert await store.scalar(select(func.count()).select_from(CatalogItem)) == 1
    assert (await store.scalars(select(CatalogItem))).one().price_text == "120000"
    assert (
        await search_public_profiles(
            store,
            PublicSearchParams(q="stomatolog", result_type="service"),
        )
    ).total == 0
    assert (
        await search_public_profiles(
            store,
            PublicSearchParams(q="Tish shifokori", result_type="service"),
        )
    ).total == 1

    payload["items"] = []
    await sync_business_catalog(
        store,
        account_id=7,
        owner_name="Muhr",
        payload=payload,
        changed_resources={"items"},
    )
    assert await store.scalar(select(func.count()).select_from(CatalogItem)) == 0


@pytest.mark.asyncio
async def test_group_link_and_same_source_id_in_two_businesses_do_not_collide(store):
    seed_business(store, 7, "Muhr")
    seed_business(store, 8, "Ziyo")

    for account_id, name in ((7, "Muhr"), (8, "Ziyo")):
        await sync_business_catalog(
            store,
            account_id=account_id,
            owner_name=name,
            payload={
                "item_groups": [
                    {"id": 1, "name": "Kurslar", "kind": "service"},
                ],
                "items": [
                    {
                        "id": 1,
                        "group_id": 1,
                        "name": f"{name} ingliz tili",
                        "kind": "service",
                    },
                ],
            },
            changed_resources={"item_groups", "items"},
        )

    groups = list((await store.scalars(select(CatalogGroup))).all())
    items = list((await store.scalars(select(CatalogItem))).all())

    assert len(groups) == 2
    assert len(items) == 2
    assert {row.source_record_key for row in groups} == {"1"}
    assert {row.source_record_key for row in items} == {"1"}
    assert len({row.id for row in items}) == 2
    assert {row.catalog_group_id for row in items} == {row.id for row in groups}


@pytest.mark.asyncio
async def test_empty_name_is_quarantined_from_public_search(store):
    seed_business(store, 7, "Muhr")
    await sync_business_catalog(
        store,
        account_id=7,
        owner_name="Muhr",
        payload={
            "item_groups": [],
            "items": [{"id": 1, "name": " ", "kind": "service"}],
        },
        changed_resources={"items"},
    )

    item = (await store.scalars(select(CatalogItem))).one()
    assert item.review_state is ReviewState.REVIEW_REQUIRED
    assert (
        await search_public_profiles(
            store,
            PublicSearchParams(q=" ", result_type="service"),
        )
    ).total == 0
