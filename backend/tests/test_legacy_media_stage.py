from datetime import UTC, datetime
from io import BytesIO
import sqlite3

import pytest
import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.catalog.model import CatalogGroup, CatalogItem
from app.core.config import Settings
from app.db.base import Base
from app.legacy_migration.media_stage import (
    LocalMediaResolver,
    MediaResolution,
    ResolvedMedia,
    TelegramMediaResolver,
    migrate_media,
    sniff_media_type,
)
from app.legacy_migration.model import (
    LegacyIdMap,
    MediaMigration,
    MediaMigrationState,
    MigrationEnvironment,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
    OwnerState,
    ReviewState,
)
from app.media.storage import StoredObject


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
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

    async def get(self, model, key, **kwargs):
        return self.sync.get(model, key)


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            MigrationRun.__table__,
            LegacyIdMap.__table__,
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
        stage=MigrationStage.MEDIA,
        status=MigrationStatus.RUNNING,
        counters_json={},
        error_count=0,
        started_at=NOW,
    )
    item = CatalogItem(
        id=10,
        business_account_id=None,
        catalog_group_id=None,
        owner_name_snapshot="Turon Savdo",
        name="Mebel",
        price_text="Kelishiladi",
        note="",
        kind="product",
        queue_enabled=False,
        image_object_key="",
        status="active",
        owner_state=OwnerState.UNLINKED,
        review_state=ReviewState.READY,
        migration_run_id=1,
        created_at=NOW,
        updated_at=NOW,
    )
    media = MediaMigration(
        id=1,
        migration_run_id=1,
        entity_type="catalog_item",
        legacy_id=8,
        slot="primary",
        source_reference_fingerprint="c" * 64,
        destination_object_key="",
        sha256="",
        content_type="",
        size_bytes=0,
        state=MediaMigrationState.PENDING,
        attempts=0,
        last_error_code="",
        created_at=NOW,
        updated_at=NOW,
    )
    mapping = LegacyIdMap(
        id=1,
        entity_type="catalog_item",
        legacy_id=8,
        target_id=10,
        source_row_hash="d" * 64,
        mapping_status="mapped",
        review_reason="",
        last_run_id=1,
    )
    session.add_all((run, item, mapping, media))
    session.commit()
    try:
        yield AsyncStore(session), run
    finally:
        session.close()
        engine.dispose()


def legacy_source(reference="uploads/mebel.png"):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE items(id INTEGER PRIMARY KEY, photo_file TEXT)"
    )
    connection.execute(
        "CREATE TABLE listing_media(id INTEGER PRIMARY KEY, tg_file_id TEXT)"
    )
    connection.execute(
        """
        CREATE TABLE advertisements(
            id INTEGER PRIMARY KEY,
            image_file TEXT,
            mobile_image_file TEXT
        )
        """
    )
    connection.execute(
        "INSERT INTO items(id, photo_file) VALUES (8, ?)",
        (reference,),
    )
    connection.commit()
    return connection


class StaticResolver:
    def __init__(self, result):
        self.result = result
        self.references = []

    async def resolve(self, reference):
        self.references.append(reference)
        return self.result


class FakeStorage:
    def __init__(self, *, verifies=True):
        self.verifies = verifies
        self.uploaded = []
        self.verified = []

    def put_migration_object(self, **kwargs):
        data = kwargs["stream"].read()
        key = (
            f"migration/{kwargs['run_id']}/{kwargs['entity_type']}/"
            f"{kwargs['legacy_id']}/{kwargs['slot']}/"
            f"{kwargs['sha256']}{kwargs['suffix']}"
        )
        self.uploaded.append((key, data))
        return StoredObject(
            object_key=key,
            size_bytes=kwargs["size_bytes"],
            sha256=kwargs["sha256"],
            content_type=kwargs["content_type"],
        )

    def verify_object(self, object_key, **kwargs):
        self.verified.append(object_key)
        return self.verifies


def resolved_png():
    return MediaResolution(
        media=ResolvedMedia(
            stream=BytesIO(PNG_BYTES),
            content_type="image/png",
            size_bytes=len(PNG_BYTES),
            sha256=(
                "9656be35bd353ebedd79d7d24a14df408ef96b99fb4e4b4542"
                "e3bdd56de73134"
            ),
        ),
        code="",
    )


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (b"\xff\xd8\xffrest", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\nrest", "image/png"),
        (b"GIF89a", "image/gif"),
        (b"RIFF1234WEBP", "image/webp"),
        (b"\x00\x00\x00\x18ftypisom", "video/mp4"),
        (b"\x1aE\xdf\xa3rest", "video/webm"),
        (b"MZ executable", None),
    ],
)
def test_sniff_media_type_uses_magic_bytes(header, expected):
    assert sniff_media_type(header) == expected


@pytest.mark.asyncio
async def test_valid_media_is_uploaded_and_verified(store):
    db, run = store
    resolver = StaticResolver(resolved_png())
    storage = FakeStorage()

    result = await migrate_media(
        db,
        legacy_source(),
        storage,
        Settings(environment="test"),
        run,
        local_resolver=resolver,
        telegram_resolver=resolver,
    )
    media = db.sync.get(MediaMigration, 1)
    item = db.sync.get(CatalogItem, 10)

    assert result.created == 1
    assert media.state is MediaMigrationState.COPIED
    assert len(media.sha256) == 64
    assert media.size_bytes == len(PNG_BYTES)
    assert media.destination_object_key.startswith("migration/1/")
    assert storage.verified == [media.destination_object_key]
    assert item.image_object_key == media.destination_object_key


@pytest.mark.asyncio
async def test_missing_media_keeps_content_and_marks_missing(store):
    db, run = store
    resolver = StaticResolver(MediaResolution(None, "media.missing"))

    await migrate_media(
        db,
        legacy_source(),
        FakeStorage(),
        Settings(environment="test"),
        run,
        local_resolver=resolver,
        telegram_resolver=resolver,
    )
    media = db.sync.get(MediaMigration, 1)
    item = db.sync.get(CatalogItem, 10)

    assert media.state is MediaMigrationState.MISSING
    assert item.image_object_key == ""


@pytest.mark.asyncio
async def test_checksum_verification_failure_blocks_media(store):
    db, run = store
    resolver = StaticResolver(resolved_png())

    await migrate_media(
        db,
        legacy_source(),
        FakeStorage(verifies=False),
        Settings(environment="test"),
        run,
        local_resolver=resolver,
        telegram_resolver=resolver,
    )
    media = db.sync.get(MediaMigration, 1)

    assert media.state is MediaMigrationState.FAILED
    assert media.last_error_code == "media.r2_verification_failed"
    assert media.attempts == 1


@pytest.mark.asyncio
async def test_path_escape_is_invalid_not_read(tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    resolver = LocalMediaResolver((uploads,))

    result = await resolver.resolve("../../etc/passwd")

    assert result.code == "media.path_outside_roots"
    assert result.media is None


@pytest.mark.asyncio
async def test_local_media_over_limit_is_invalid(tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "large.png").write_bytes(PNG_BYTES)
    resolver = LocalMediaResolver((uploads,), max_bytes=8)

    result = await resolver.resolve("uploads/large.png")

    assert result.code == "media.too_large"
    assert result.media is None


@pytest.mark.asyncio
async def test_telegram_404_returns_safe_error_code():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(404, request=request)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        resolver = TelegramMediaResolver("secret-token", client=client)
        result = await resolver.resolve("secret-file-id")

    assert result.code == "media.telegram_failed"
    assert result.media is None
