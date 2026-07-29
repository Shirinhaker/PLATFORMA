from datetime import UTC, datetime
import sqlite3

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.advertisements.model import Advertisement
from app.db.base import Base
from app.legacy_migration.listing_stage import import_listings
from app.legacy_migration.model import (
    LegacyIdMap,
    MediaMigration,
    MigrationEnvironment,
    MigrationIssue,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
    ReviewState,
)
from app.listings.model import Listing, ListingMedia


NOW = datetime(2026, 7, 29, tzinfo=UTC)


class AsyncStore:
    def __init__(self, session):
        self.sync = session
        self.sequences = {}

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
            LegacyIdMap.__table__,
            MigrationIssue.__table__,
            MediaMigration.__table__,
            Listing.__table__,
            ListingMedia.__table__,
            Advertisement.__table__,
        ),
    )
    session = Session(engine, expire_on_commit=False)
    run = MigrationRun(
        id=1,
        source_database_sha256="a" * 64,
        media_manifest_sha256="b" * 64,
        schema_version="0003_phase3c_content",
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.LISTINGS,
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
    listing: dict[str, object] | None = None,
    media: list[dict[str, object]] | None = None,
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE listings (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            business_id INTEGER,
            cat TEXT,
            title TEXT,
            price TEXT,
            descr TEXT,
            address TEXT,
            lat REAL,
            lng REAL,
            visibility TEXT,
            status TEXT,
            created_at INTEGER
        );
        CREATE TABLE listing_media (
            id INTEGER PRIMARY KEY,
            listing_id INTEGER,
            tg_file_id TEXT,
            mtype TEXT,
            pos INTEGER
        );
        """
    )
    if listing is not None:
        row = {
            "id": 11,
            "user_id": 7,
            "business_id": None,
            "cat": "uy",
            "title": "Hovli sotiladi",
            "price": "Kelishiladi",
            "descr": "Qulay joyda",
            "address": "Qumqo‘rg‘on",
            "lat": 37.8,
            "lng": 67.5,
            "visibility": "all",
            "status": "active",
            "created_at": 1_722_211_200,
        } | listing
        connection.execute(
            """
            INSERT INTO listings(
                id, user_id, business_id, cat, title, price, descr, address,
                lat, lng, visibility, status, created_at
            ) VALUES (
                :id, :user_id, :business_id, :cat, :title, :price, :descr,
                :address, :lat, :lng, :visibility, :status, :created_at
            )
            """,
            row,
        )
    for supplied in media or []:
        row = {
            "id": 21,
            "listing_id": 11,
            "tg_file_id": "telegram-file-secret",
            "mtype": "photo",
            "pos": 0,
        } | supplied
        connection.execute(
            """
            INSERT INTO listing_media(id, listing_id, tg_file_id, mtype, pos)
            VALUES (:id, :listing_id, :tg_file_id, :mtype, :pos)
            """,
            row,
        )
    connection.commit()
    return connection


def seed_mapping(
    db: AsyncStore,
    run: MigrationRun,
    *,
    entity_type: str,
    legacy_id: int,
    target_id: int,
    account_type: AccountType,
):
    if db.sync.get(Account, target_id) is None:
        db.sync.add(
            Account(
                id=target_id,
                account_type=account_type,
                login=f"{account_type.value}_{target_id}",
                password_hash="hash",
                telegram_user_id=None,
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        )
    db.sync.add(
        LegacyIdMap(
            id=legacy_id,
            entity_type=entity_type,
            legacy_id=legacy_id,
            target_id=target_id,
            source_row_hash="c" * 64,
            mapping_status="mapped",
            review_reason="",
            last_run_id=run.id,
        )
    )
    db.sync.commit()


@pytest.mark.asyncio
async def test_listing_and_media_metadata_are_distinct_from_ads(store):
    db, run = store
    seed_mapping(
        db,
        run,
        entity_type="user_account",
        legacy_id=7,
        target_id=70,
        account_type=AccountType.USER,
    )
    source = source_with({}, [{}])

    result = await import_listings(db, source, run)
    listing = (await db.scalars(select(Listing))).one()
    media = list(
        await db.scalars(select(ListingMedia).order_by(ListingMedia.position))
    )

    assert result.created == 2
    assert listing.price_text == "Kelishiladi"
    assert listing.visibility == "all"
    assert listing.owner_user_account_id == 70
    assert [item.position for item in media] == [0]
    assert media[0].object_key == ""
    assert media[0].migration_state == "pending"
    assert (
        await db.scalar(select(func.count()).select_from(Advertisement))
    ) == 0


@pytest.mark.asyncio
async def test_optional_business_owner_is_mapped_separately(store):
    db, run = store
    seed_mapping(
        db,
        run,
        entity_type="user_account",
        legacy_id=7,
        target_id=70,
        account_type=AccountType.USER,
    )
    seed_mapping(
        db,
        run,
        entity_type="business_account",
        legacy_id=3,
        target_id=30,
        account_type=AccountType.BUSINESS,
    )
    source = source_with({"business_id": 3})

    await import_listings(db, source, run)
    listing = (await db.scalars(select(Listing))).one()

    assert listing.owner_user_account_id == 70
    assert listing.owner_business_account_id == 30


@pytest.mark.asyncio
async def test_missing_required_fields_are_hidden_and_reported(store):
    db, run = store
    source = source_with({"title": " ", "cat": ""})

    await import_listings(db, source, run)
    listing = (await db.scalars(select(Listing))).one()
    codes = list(await db.scalars(select(MigrationIssue.issue_code)))

    assert listing.review_state is ReviewState.REVIEW_REQUIRED
    assert "listing.required.title" in codes
    assert "listing.required.category" in codes


@pytest.mark.asyncio
async def test_media_reference_is_only_fingerprinted(store):
    db, run = store
    source = source_with({}, [{"mtype": "video", "pos": 2}])

    await import_listings(db, source, run)
    listing_media = (await db.scalars(select(ListingMedia))).one()
    migration = (await db.scalars(select(MediaMigration))).one()

    assert listing_media.media_type == "video"
    assert listing_media.position == 2
    assert migration.entity_type == "listing_media"
    assert migration.legacy_id == 21
    assert migration.slot == "primary"
    assert len(migration.source_reference_fingerprint) == 64
    assert "telegram-file-secret" not in migration.source_reference_fingerprint


@pytest.mark.asyncio
async def test_rerun_is_idempotent_and_changed_status_updates(store):
    db, run = store
    source = source_with({})

    first = await import_listings(db, source, run)
    second = await import_listings(db, source, run)
    source.execute("UPDATE listings SET status = 'deleted' WHERE id = 11")
    source.commit()
    third = await import_listings(db, source, run)
    listing = (await db.scalars(select(Listing))).one()

    assert first.created == 1
    assert second.created == 0
    assert third.updated == 1
    assert listing.status == "deleted"
    assert await db.scalar(select(func.count()).select_from(Listing)) == 1


@pytest.mark.asyncio
async def test_reused_listing_targets_move_to_current_migration_run(store):
    db, first_run = store
    source = source_with({}, [{"mtype": "photo", "pos": 1}])
    await import_listings(db, source, first_run)
    current_run = MigrationRun(
        id=2,
        source_database_sha256="a" * 64,
        media_manifest_sha256="b" * 64,
        schema_version="0003_phase3c_dual_accounts_v2",
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.LISTINGS,
        status=MigrationStatus.RUNNING,
        counters_json={},
        error_count=0,
        started_at=NOW,
    )
    db.sync.add(current_run)
    db.sync.commit()

    result = await import_listings(db, source, current_run)
    listing = (await db.scalars(select(Listing))).one()
    media = (await db.scalars(select(ListingMedia))).one()
    media_migration = (await db.scalars(select(MediaMigration))).one()

    assert result.created == 0
    assert result.reused == 2
    assert listing.migration_run_id == current_run.id
    assert media.migration_run_id == current_run.id
    assert media_migration.migration_run_id == current_run.id


@pytest.mark.asyncio
async def test_reused_listing_refreshes_owner_after_account_split(store):
    db, first_run = store
    seed_mapping(
        db,
        first_run,
        entity_type="user_account",
        legacy_id=7,
        target_id=30,
        account_type=AccountType.BUSINESS,
    )
    source = source_with({})
    await import_listings(db, source, first_run)
    mapping = db.sync.scalar(
        select(LegacyIdMap).where(
            LegacyIdMap.entity_type == "user_account",
            LegacyIdMap.legacy_id == 7,
        )
    )
    db.sync.add(
        Account(
            id=70,
            account_type=AccountType.USER,
            login="user_70",
            password_hash="hash",
            telegram_user_id=None,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    mapping.target_id = 70
    current_run = MigrationRun(
        id=2,
        source_database_sha256="a" * 64,
        media_manifest_sha256="b" * 64,
        schema_version="0003_phase3c_dual_accounts_v2",
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.LISTINGS,
        status=MigrationStatus.RUNNING,
        counters_json={},
        error_count=0,
        started_at=NOW,
    )
    db.sync.add(current_run)
    db.sync.commit()

    result = await import_listings(db, source, current_run)
    listing = (await db.scalars(select(Listing))).one()

    assert result.updated == 1
    assert listing.owner_user_account_id == 70
    assert listing.migration_run_id == current_run.id
