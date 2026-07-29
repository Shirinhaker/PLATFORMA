from datetime import UTC, datetime
import sqlite3

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.catalog.model import CatalogGroup, CatalogItem
from app.db.base import Base
from app.legacy_migration.catalog_stage import import_catalog
from app.legacy_migration.model import (
    LegacyIdMap,
    MediaMigration,
    MediaMigrationState,
    MigrationEnvironment,
    MigrationIssue,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
    OwnerState,
    ReviewState,
)
from app.profiles.model import BusinessProfile


NOW = datetime(2026, 7, 29, tzinfo=UTC)


class AsyncStore:
    def __init__(self, session: Session):
        self.sync = session
        self.sequences: dict[str, int] = {}

    def add(self, value):
        self.sync.add(value)

    async def flush(self):
        for value in list(self.sync.new):
            if not hasattr(value, "id") or value.id is not None:
                continue
            table = value.__table__.name
            if table not in self.sequences:
                highest = self.sync.scalar(
                    select(func.max(value.__table__.c.id))
                )
                self.sequences[table] = int(highest or 0)
            self.sequences[table] += 1
            value.id = self.sequences[table]
        self.sync.flush()

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def get(self, model, key, **kwargs):
        return self.sync.get(model, key)


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            MigrationRun.__table__,
            Account.__table__,
            BusinessProfile.__table__,
            LegacyIdMap.__table__,
            MigrationIssue.__table__,
            MediaMigration.__table__,
            CatalogGroup.__table__,
            CatalogItem.__table__,
        ),
    )
    session = Session(engine, expire_on_commit=False)
    run = MigrationRun(
        id=1,
        source_database_sha256="a" * 64,
        media_manifest_sha256="b" * 64,
        schema_version="0003_phase3c_content",
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.CATALOG,
        status=MigrationStatus.RUNNING,
        counters_json={},
        error_count=0,
        started_at=NOW,
    )
    session.add(run)
    session.commit()
    try:
        yield AsyncStore(session), run
    finally:
        session.close()
        engine.dispose()


def source_with(
    *,
    group: dict[str, object] | None = None,
    item: dict[str, object] | None = None,
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE businesses (
            id INTEGER PRIMARY KEY,
            name TEXT
        );
        CREATE TABLE item_groups (
            id INTEGER PRIMARY KEY,
            business_id INTEGER,
            name TEXT,
            kind TEXT,
            status TEXT,
            created_at INTEGER
        );
        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            business_id INTEGER,
            group_id INTEGER,
            name TEXT,
            price TEXT,
            note TEXT,
            kind TEXT,
            queue_enabled INTEGER,
            photo_file TEXT,
            status TEXT,
            created_at INTEGER
        );
        INSERT INTO businesses(id, name) VALUES (3, 'Turon Savdo');
        """
    )
    if group is not None:
        data = {
            "id": 4,
            "business_id": 3,
            "name": "Mebellar",
            "kind": "product",
            "status": "active",
            "created_at": 1_722_211_200,
        } | group
        connection.execute(
            """
            INSERT INTO item_groups(
                id, business_id, name, kind, status, created_at
            ) VALUES (
                :id, :business_id, :name, :kind, :status, :created_at
            )
            """,
            data,
        )
    if item is not None:
        data = {
            "id": 8,
            "business_id": 3,
            "group_id": 4 if group is not None else None,
            "name": "Mebel",
            "price": "1 500 000 so'mdan",
            "note": "Buyurtma asosida",
            "kind": "product",
            "queue_enabled": 0,
            "photo_file": "uploads/mebel.webp",
            "status": "active",
            "created_at": 1_722_211_200,
        } | item
        connection.execute(
            """
            INSERT INTO items(
                id, business_id, group_id, name, price, note, kind,
                queue_enabled, photo_file, status, created_at
            ) VALUES (
                :id, :business_id, :group_id, :name, :price, :note, :kind,
                :queue_enabled, :photo_file, :status, :created_at
            )
            """,
            data,
        )
    connection.commit()
    return connection


def seed_owner(store: AsyncStore, run: MigrationRun):
    account = Account(
        id=30,
        account_type=AccountType.BUSINESS,
        login="b_turon",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )
    profile = BusinessProfile(
        account_id=30,
        name="Turon Savdo",
        phone="",
        description="",
        public_username="",
        direction="Savdo",
        activity_type="Mebel",
        address="Qumqo‘rg‘on",
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
    )
    mapping = LegacyIdMap(
        id=1,
        entity_type="business_account",
        legacy_id=3,
        target_id=30,
        source_row_hash="c" * 64,
        mapping_status="mapped",
        review_reason="",
        last_run_id=run.id,
    )
    store.sync.add_all((account, profile, mapping))
    store.sync.commit()


async def issue_codes(store: AsyncStore) -> list[str]:
    return list(
        await store.scalars(
            select(MigrationIssue.issue_code).order_by(MigrationIssue.id)
        )
    )


@pytest.mark.asyncio
async def test_catalog_keeps_price_kind_status_and_owner(store):
    db, run = store
    seed_owner(db, run)
    source = source_with(group={}, item={})

    result = await import_catalog(db, source, run)
    item = (
        await db.scalars(
            select(CatalogItem).where(CatalogItem.name == "Mebel")
        )
    ).one()

    assert result.created == 2
    assert item.price_text == "1 500 000 so'mdan"
    assert item.kind == "product"
    assert item.status == "active"
    assert item.owner_state is OwnerState.LINKED
    assert item.business_account_id == 30
    assert item.review_state is ReviewState.READY
    assert item.created_at.replace(tzinfo=UTC) == datetime(
        2024,
        7,
        29,
        tzinfo=UTC,
    )


@pytest.mark.asyncio
async def test_unlinked_owner_item_is_visible_but_has_no_owner_id(store):
    db, run = store
    source = source_with(item={"kind": "service", "queue_enabled": 1})

    await import_catalog(db, source, run)
    item = (await db.scalars(select(CatalogItem))).one()

    assert item.owner_state is OwnerState.UNLINKED
    assert item.business_account_id is None
    assert item.owner_name_snapshot == "Turon Savdo"
    assert item.review_state is ReviewState.READY
    assert item.queue_enabled is True


@pytest.mark.asyncio
async def test_missing_required_name_is_quarantined(store):
    db, run = store
    source = source_with(item={"name": "   "})

    await import_catalog(db, source, run)
    item = (await db.scalars(select(CatalogItem))).one()

    assert item.review_state is ReviewState.REVIEW_REQUIRED
    assert "catalog.required.name" in await issue_codes(db)


@pytest.mark.asyncio
async def test_unknown_kind_is_hidden_and_reported(store):
    db, run = store
    source = source_with(item={"kind": "mystery"})

    await import_catalog(db, source, run)
    item = (await db.scalars(select(CatalogItem))).one()

    assert item.review_state is ReviewState.REVIEW_REQUIRED
    assert "catalog.required.kind" in await issue_codes(db)


@pytest.mark.asyncio
async def test_photo_creates_pending_media_without_leaking_reference(store):
    db, run = store
    source = source_with(item={"photo_file": "telegram-secret-reference"})

    await import_catalog(db, source, run)
    item = (await db.scalars(select(CatalogItem))).one()
    media = (await db.scalars(select(MediaMigration))).one()

    assert item.image_object_key == ""
    assert media.entity_type == "catalog_item"
    assert media.legacy_id == 8
    assert media.slot == "primary"
    assert media.state is MediaMigrationState.PENDING
    assert "telegram-secret-reference" not in media.source_reference_fingerprint
    assert len(media.source_reference_fingerprint) == 64


@pytest.mark.asyncio
async def test_changed_source_updates_and_identical_rerun_creates_zero(store):
    db, run = store
    source = source_with(item={})

    first = await import_catalog(db, source, run)
    second = await import_catalog(db, source, run)
    source.execute(
        "UPDATE items SET price = ? WHERE id = 8",
        ("Kelishiladi",),
    )
    source.commit()
    third = await import_catalog(db, source, run)
    item = (await db.scalars(select(CatalogItem))).one()

    assert first.created == 1
    assert second.created == 0
    assert third.updated == 1
    assert item.price_text == "Kelishiladi"
    assert (
        await db.scalar(select(func.count()).select_from(CatalogItem))
    ) == 1


@pytest.mark.asyncio
async def test_reused_catalog_targets_move_to_current_migration_run(store):
    db, first_run = store
    source = source_with(group={}, item={})
    await import_catalog(db, source, first_run)
    current_run = MigrationRun(
        id=2,
        source_database_sha256="a" * 64,
        media_manifest_sha256="b" * 64,
        schema_version="0003_phase3c_dual_accounts_v2",
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.CATALOG,
        status=MigrationStatus.RUNNING,
        counters_json={},
        error_count=0,
        started_at=NOW,
    )
    db.sync.add(current_run)
    db.sync.commit()

    result = await import_catalog(db, source, current_run)
    group = (await db.scalars(select(CatalogGroup))).one()
    item = (await db.scalars(select(CatalogItem))).one()
    media = (await db.scalars(select(MediaMigration))).one()

    assert result.created == 0
    assert result.reused == 2
    assert group.migration_run_id == current_run.id
    assert item.migration_run_id == current_run.id
    assert media.migration_run_id == current_run.id
