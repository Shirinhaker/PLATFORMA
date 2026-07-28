from datetime import UTC, datetime, time
import sqlite3

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.advertisements.model import Advertisement
from app.db.base import Base
from app.legacy_migration.advertisement_stage import import_advertisements
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
from app.profiles.model import BusinessProfile


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
                maximum = self.sync.scalar(
                    select(func.max(value.__table__.c.id))
                )
                self.sequences[table] = int(maximum or 0)
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
        stage=MigrationStage.ADVERTISEMENTS,
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


def source_with(overrides: dict[str, object] | None = None):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE advertisements (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            business_id INTEGER,
            actor_type TEXT,
            title TEXT,
            caption TEXT,
            image_file TEXT,
            mobile_image_file TEXT,
            crop_x REAL,
            crop_y REAL,
            crop_zoom REAL,
            daily_all_day INTEGER,
            daily_start TEXT,
            daily_end TEXT,
            targets_json TEXT,
            start_at INTEGER,
            end_at INTEGER,
            duration_days INTEGER,
            price INTEGER,
            district_count INTEGER,
            hours_per_day INTEGER,
            district_hour_rate INTEGER,
            billable_district_hours INTEGER,
            price_code TEXT,
            status TEXT,
            views INTEGER,
            clicks INTEGER,
            created_at INTEGER,
            updated_at INTEGER
        )
        """
    )
    row = {
        "id": 5,
        "user_id": 7,
        "business_id": None,
        "actor_type": "business",
        "title": "Turon Savdo",
        "caption": "Yangi mebellar",
        "image_file": "/uploads/ads/desktop.webp",
        "mobile_image_file": "/uploads/ads/mobile.webp",
        "crop_x": 48.0,
        "crop_y": 52.0,
        "crop_zoom": 1.2,
        "daily_all_day": 0,
        "daily_start": "18:00",
        "daily_end": "19:00",
        "targets_json": (
            '[{"region":"Surxondaryo","district":"Qumqo‘rg‘on"}]'
        ),
        "start_at": 1_722_211_200,
        "end_at": 1_722_297_600,
        "duration_days": 1,
        "price": 350_000,
        "district_count": 7,
        "hours_per_day": 1,
        "district_hour_rate": 50_000,
        "billable_district_hours": 7,
        "price_code": "advertisement_district_hour",
        "status": "active",
        "views": 12,
        "clicks": 3,
        "created_at": 1_722_211_200,
        "updated_at": 1_722_211_200,
    } | (overrides or {})
    columns = ", ".join(row)
    placeholders = ", ".join(f":{key}" for key in row)
    connection.execute(
        f"INSERT INTO advertisements ({columns}) VALUES ({placeholders})",
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
async def test_ad_snapshot_is_not_repriced_or_turned_into_business(store):
    db, run = store
    source = source_with()

    await import_advertisements(db, source, run)
    ad = (await db.scalars(select(Advertisement))).one()

    assert ad.title == "Turon Savdo"
    assert ad.owner_business_account_id is None
    assert ad.price == 350_000
    assert ad.district_count == 7
    assert ad.hours_per_day == 1
    assert ad.district_hour_rate == 50_000
    assert ad.billable_district_hours == 7
    assert ad.targets_json == [
        {"region": "Surxondaryo", "district": "Qumqo‘rg‘on"}
    ]
    assert (
        await db.scalar(select(func.count()).select_from(BusinessProfile))
    ) == 0


@pytest.mark.asyncio
async def test_schedule_crop_statistics_and_owner_mapping_are_preserved(store):
    db, run = store
    seed_mapping(
        db,
        run,
        entity_type="user_account",
        legacy_id=7,
        target_id=70,
        account_type=AccountType.USER,
    )
    source = source_with({"actor_type": "user"})

    await import_advertisements(db, source, run)
    ad = (await db.scalars(select(Advertisement))).one()

    assert ad.owner_user_account_id == 70
    assert ad.owner_business_account_id is None
    assert ad.daily_all_day is False
    assert ad.daily_start == time(18, 0)
    assert ad.daily_end == time(19, 0)
    assert ad.crop_x == 48.0
    assert ad.crop_y == 52.0
    assert ad.crop_zoom == 1.2
    assert ad.views == 12
    assert ad.clicks == 3


@pytest.mark.asyncio
async def test_desktop_and_mobile_media_slots_are_separate(store):
    db, run = store
    source = source_with()

    await import_advertisements(db, source, run)
    slots = list(
        await db.scalars(
            select(MediaMigration).order_by(MediaMigration.slot)
        )
    )

    assert [item.slot for item in slots] == ["desktop", "mobile"]
    assert all(item.entity_type == "advertisement" for item in slots)
    assert all(item.legacy_id == 5 for item in slots)
    assert all(len(item.source_reference_fingerprint) == 64 for item in slots)
    assert all(not item.destination_object_key for item in slots)


@pytest.mark.asyncio
async def test_malformed_targets_and_time_are_hidden_and_reported(store):
    db, run = store
    source = source_with(
        {
            "targets_json": "{not-json",
            "daily_start": "99:99",
        }
    )

    await import_advertisements(db, source, run)
    ad = (await db.scalars(select(Advertisement))).one()
    codes = list(await db.scalars(select(MigrationIssue.issue_code)))

    assert ad.review_state is ReviewState.REVIEW_REQUIRED
    assert ad.targets_json == []
    assert "advertisement.targets_invalid" in codes
    assert "advertisement.daily_time_invalid" in codes


@pytest.mark.asyncio
async def test_rerun_is_idempotent_and_changed_snapshot_updates(store):
    db, run = store
    source = source_with()

    first = await import_advertisements(db, source, run)
    second = await import_advertisements(db, source, run)
    source.execute("UPDATE advertisements SET views = 99 WHERE id = 5")
    source.commit()
    third = await import_advertisements(db, source, run)
    ad = (await db.scalars(select(Advertisement))).one()

    assert first.created == 1
    assert second.created == 0
    assert third.updated == 1
    assert ad.views == 99
    assert (
        await db.scalar(select(func.count()).select_from(Advertisement))
    ) == 1
