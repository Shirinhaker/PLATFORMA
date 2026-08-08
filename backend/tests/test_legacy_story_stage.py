from datetime import UTC, datetime
import sqlite3

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.db.base import Base
from app.legacy_migration.model import (
    LegacyIdMap,
    MediaMigration,
    MigrationEnvironment,
    MigrationIssue,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
)
from app.legacy_migration.story_stage import import_stories
from app.stories.model import Story, StoryReport, StoryView


NOW = datetime(2026, 8, 8, tzinfo=UTC)


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
                highest = self.sync.scalar(select(func.max(value.__table__.c.id)))
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
            Story.__table__,
            StoryView.__table__,
            StoryReport.__table__,
        ),
    )
    session = Session(engine, expire_on_commit=False)
    run = MigrationRun(
        id=1,
        source_database_sha256="a" * 64,
        media_manifest_sha256="b" * 64,
        schema_version="0006_phase3c_complete_cabinet_v1",
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


def source_with_story(**overrides) -> sqlite3.Connection:
    source = sqlite3.connect(":memory:")
    source.row_factory = sqlite3.Row
    source.executescript(
        """
        CREATE TABLE stories (
            id INTEGER PRIMARY KEY,
            owner_type TEXT,
            owner_id INTEGER,
            created_by_user_id INTEGER,
            media_type TEXT,
            media_filename TEXT,
            thumbnail_filename TEXT,
            mime_type TEXT,
            caption TEXT,
            duration_seconds REAL,
            status TEXT,
            created_at INTEGER,
            expires_at INTEGER,
            deleted_at INTEGER
        );
        CREATE TABLE story_views (
            story_id INTEGER,
            viewer_user_id INTEGER,
            viewed_at INTEGER
        );
        CREATE TABLE story_reports (
            id INTEGER PRIMARY KEY,
            story_id INTEGER,
            reporter_user_id INTEGER,
            reason TEXT,
            status TEXT,
            created_at INTEGER
        );
        """
    )
    row = {
        "id": 11,
        "owner_type": "user",
        "owner_id": 7,
        "created_by_user_id": 7,
        "media_type": "video",
        "media_filename": "story.mp4",
        "thumbnail_filename": "story.jpg",
        "mime_type": "video/mp4",
        "caption": "Bugungi yangilik",
        "duration_seconds": 15.5,
        "status": "active",
        "created_at": 1_722_211_200,
        "expires_at": 1_722_297_600,
        "deleted_at": 0,
    } | overrides
    columns = ", ".join(row)
    placeholders = ", ".join(f":{key}" for key in row)
    source.execute(
        f"INSERT INTO stories ({columns}) VALUES ({placeholders})",
        row,
    )
    source.execute(
        "INSERT INTO story_views VALUES (11, 8, 1722211300)"
    )
    source.execute(
        "INSERT INTO story_reports VALUES (3, 11, 8, ?, 'new', 1722211400)",
        ("Nomaqbul kontent sababi",),
    )
    source.commit()
    return source


def seed_account_mapping(
    db: AsyncStore,
    run: MigrationRun,
    *,
    entity_type: str,
    legacy_id: int,
    target_id: int,
    account_type: AccountType,
) -> None:
    if db.sync.get(Account, target_id) is None:
        db.sync.add(Account(
            id=target_id,
            account_type=account_type,
            login=f"{account_type.value}_{target_id}",
            password_hash="hash",
            telegram_user_id=None,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        ))
    db.sync.add(LegacyIdMap(
        id=legacy_id,
        entity_type=entity_type,
        legacy_id=legacy_id,
        target_id=target_id,
        source_row_hash="c" * 64,
        mapping_status="mapped",
        review_reason="",
        last_run_id=run.id,
    ))
    db.sync.commit()


@pytest.mark.asyncio
async def test_story_views_reports_and_media_are_imported_idempotently(store):
    db, run = store
    seed_account_mapping(
        db, run,
        entity_type="user_account", legacy_id=7, target_id=70,
        account_type=AccountType.USER,
    )
    seed_account_mapping(
        db, run,
        entity_type="user_account", legacy_id=8, target_id=80,
        account_type=AccountType.USER,
    )
    source = source_with_story()

    first = await import_stories(db, source, run)
    second = await import_stories(db, source, run)
    story = (await db.scalars(select(Story))).one()
    media = list(await db.scalars(select(MediaMigration).order_by(MediaMigration.slot)))

    assert first.created == 3
    assert second.created == 0
    assert story.owner_account_id == 70
    assert story.status == "processing"
    assert story.duration_seconds == 15.5
    assert [item.slot for item in media] == ["primary", "thumbnail"]
    assert await db.scalar(select(func.count()).select_from(StoryView)) == 1
    assert await db.scalar(select(func.count()).select_from(StoryReport)) == 1
    assert await db.scalar(
        select(func.count(LegacyIdMap.id)).where(LegacyIdMap.entity_type == "story")
    ) == 1


@pytest.mark.asyncio
async def test_unresolved_story_is_quarantined_without_creating_content(store):
    db, run = store
    source = source_with_story(owner_id=999, media_filename="")

    result = await import_stories(db, source, run)
    mapping = await db.scalar(
        select(LegacyIdMap).where(LegacyIdMap.entity_type == "story")
    )
    codes = set(await db.scalars(select(MigrationIssue.issue_code)))

    assert result.quarantined >= 1
    assert mapping.mapping_status == "quarantined"
    assert mapping.target_id is None
    assert "story.owner_unresolved" in codes
    assert "story.media_missing" in codes
    assert await db.scalar(select(func.count()).select_from(Story)) == 0
