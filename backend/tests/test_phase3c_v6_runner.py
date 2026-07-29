from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.legacy_migration.model import (
    MigrationEnvironment,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
)
from app.legacy_migration.runner_v6 import (
    MIGRATION_SCHEMA_VERSION,
    build_database_runner,
)
from app.legacy_migration.source import SnapshotInfo, file_sha256


def snapshot(tmp_path: Path) -> SnapshotInfo:
    database = tmp_path / "platforma.snapshot.db"
    manifest = tmp_path / "media-manifest.json"
    database.write_bytes(b"database")
    manifest.write_bytes(b"[]")
    return SnapshotInfo(
        path=database,
        database_sha256=file_sha256(database),
        manifest_path=manifest,
        manifest_sha256=file_sha256(manifest),
    )


class Context:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class Session:
    def __init__(self, existing):
        self.existing = existing
        self.added = []

    def begin(self):
        return Context(self)

    async def scalar(self, statement):
        return self.existing

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for index, value in enumerate(self.added, start=50):
            if value.id is None:
                value.id = index


class Database:
    def __init__(self, existing):
        self.session_value = Session(existing)

    def session(self):
        return Context(self.session_value)


@pytest.mark.asyncio
async def test_complete_cabinet_runner_does_not_reuse_profile_parity_run(
    tmp_path,
):
    info = snapshot(tmp_path)
    previous = MigrationRun(
        id=5,
        source_database_sha256=info.database_sha256,
        media_manifest_sha256=info.manifest_sha256,
        schema_version="0005_phase3c_profile_cabinet_parity_v1",
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.VERIFY,
        status=MigrationStatus.COMPLETED,
        counters_json={"verify": {"passed": True}},
        error_count=0,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    database = Database(previous)
    runner = build_database_runner(database, object(), object())

    current = await runner.load_or_create(info, "staging", None)

    assert MIGRATION_SCHEMA_VERSION == "0006_phase3c_complete_cabinet_v1"
    assert current is not previous
    assert current.schema_version == MIGRATION_SCHEMA_VERSION
    assert current.stage is MigrationStage.SNAPSHOT
    assert current.status is MigrationStatus.RUNNING
    assert database.session_value.added == [current]
