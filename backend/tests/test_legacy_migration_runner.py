from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.legacy_migration.model import (
    MigrationEnvironment,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
)
from app.legacy_migration.runner import (
    MigrationRunner,
    ProductionApproval,
    ProductionGateError,
    STAGES,
)
from app.legacy_migration.source import SnapshotInfo
from app.legacy_migration.verify import VerificationReport


def snapshot(tmp_path: Path) -> SnapshotInfo:
    database = tmp_path / "platforma.snapshot.db"
    manifest = tmp_path / "media-manifest.json"
    database.write_bytes(b"database")
    manifest.write_bytes(b"[]")
    from app.legacy_migration.source import file_sha256

    return SnapshotInfo(
        path=database,
        database_sha256=file_sha256(database),
        manifest_path=manifest,
        manifest_sha256=file_sha256(manifest),
    )


def migration_run(info: SnapshotInfo, environment="staging"):
    return MigrationRun(
        id=1,
        source_database_sha256=info.database_sha256,
        media_manifest_sha256=info.manifest_sha256,
        schema_version="0003_phase3c_content",
        environment=MigrationEnvironment(environment),
        stage=MigrationStage.SNAPSHOT,
        status=MigrationStatus.RUNNING,
        counters_json={},
        error_count=0,
        started_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_runner_executes_fixed_order_and_resumes(tmp_path):
    info = snapshot(tmp_path)
    run = migration_run(info)
    calls = []

    async def load_or_create(snapshot_info, environment, approval):
        return run

    async def save(value):
        return value

    async def stage_handler(snapshot_info, value):
        stage = STAGES[len(calls)].stage
        calls.append(stage.value)
        if stage is MigrationStage.VERIFY:
            return VerificationReport(passed=True, gates=[])
        return {"created": 1 if stage is MigrationStage.CATALOG else 0}

    handlers = {definition.stage: stage_handler for definition in STAGES}
    runner = MigrationRunner(
        load_or_create=load_or_create,
        save=save,
        stage_handlers=handlers,
    )

    first = await runner.run(info, "staging", until_stage="catalog")
    assert first.stage is MigrationStage.CATALOG
    assert calls == ["inventory", "accounts", "businesses", "catalog"]

    second = await runner.run(info, "staging")
    assert second.stage is MigrationStage.VERIFY
    assert second.status is MigrationStatus.COMPLETED
    assert second.counters_json["catalog"]["created"] == 1
    assert calls == [
        "inventory",
        "accounts",
        "businesses",
        "catalog",
        "listings",
        "advertisements",
        "media",
        "verify",
    ]


@pytest.mark.asyncio
async def test_production_requires_explicit_confirmation(tmp_path):
    info = snapshot(tmp_path)
    run = migration_run(info, "production")

    async def load_or_create(snapshot_info, environment, approval):
        return run

    runner = MigrationRunner(
        load_or_create=load_or_create,
        save=lambda value: value,
        stage_handlers={},
    )

    with pytest.raises(
        ProductionGateError,
        match="production_confirmation_required",
    ):
        await runner.run(info, "production")


@pytest.mark.asyncio
async def test_production_approval_must_match_snapshot(tmp_path):
    info = snapshot(tmp_path)
    run = migration_run(info, "production")

    async def load_or_create(snapshot_info, environment, approval):
        return run

    runner = MigrationRunner(
        load_or_create=load_or_create,
        save=lambda value: value,
        stage_handlers={},
    )
    approval = ProductionApproval(
        typed_environment="production",
        typed_snapshot_sha256="0" * 64,
        maintenance_enabled=True,
        approved_staging_run_id=4,
    )

    with pytest.raises(
        ProductionGateError,
        match="production_snapshot_confirmation_mismatch",
    ):
        await runner.run(info, "production", approval=approval)

