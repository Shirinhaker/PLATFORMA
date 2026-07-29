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
    build_database_runner,
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


class FakeSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class ExistingRunSession:
    def __init__(self, existing):
        self.existing = existing
        self.added = []

    def begin(self):
        return FakeSessionContext(self)

    async def scalar(self, statement):
        return self.existing

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for index, value in enumerate(self.added, start=10):
            if value.id is None:
                value.id = index


class ExistingRunDatabase:
    def __init__(self, existing):
        self.session_value = ExistingRunSession(existing)

    def session(self):
        return FakeSessionContext(self.session_value)


@pytest.mark.asyncio
async def test_dual_account_migration_does_not_reuse_old_schema_run(tmp_path):
    info = snapshot(tmp_path)
    old_run = migration_run(info)
    old_run.schema_version = "0003_phase3c_dual_accounts_v2"
    old_run.stage = MigrationStage.VERIFY
    old_run.status = MigrationStatus.COMPLETED
    database = ExistingRunDatabase(old_run)
    runner = build_database_runner(database, object(), object())

    current = await runner.load_or_create(info, "staging", None)

    assert current is not old_run
    assert current.schema_version == "0003_phase3c_dual_accounts_v3"
    assert database.session_value.added == [current]


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
async def test_failed_verify_run_resumes_from_media_with_same_run_id(
    tmp_path,
):
    info = snapshot(tmp_path)
    run = migration_run(info)
    run.stage = MigrationStage.VERIFY
    run.status = MigrationStatus.FAILED
    run.finished_at = datetime.now(UTC)
    run.counters_json = {
        "catalog": {"created": 3},
        "media": {"created": 0},
        "verify": {"passed": False},
    }
    calls = []

    async def load_or_create(snapshot_info, environment, approval):
        return run

    async def save(value):
        return value

    def handler(stage):
        async def execute(snapshot_info, value):
            calls.append(stage.value)
            if stage is MigrationStage.VERIFY:
                return VerificationReport(passed=True, gates=[])
            return {"created": 0, "reused": 2}

        return execute

    runner = MigrationRunner(
        load_or_create=load_or_create,
        save=save,
        stage_handlers={
            MigrationStage.MEDIA: handler(MigrationStage.MEDIA),
            MigrationStage.VERIFY: handler(MigrationStage.VERIFY),
        },
    )

    resumed = await runner.run(info, "staging")

    assert resumed.id == 1
    assert calls == ["media", "verify"]
    assert resumed.status is MigrationStatus.COMPLETED
    assert resumed.counters_json["catalog"] == {"created": 3}
    assert resumed.counters_json["media"] == {
        "created": 0,
        "reused": 2,
    }
    assert resumed.counters_json["verify"]["passed"] is True


@pytest.mark.asyncio
async def test_failed_verify_resume_clears_finished_at_before_media_save(
    tmp_path,
):
    info = snapshot(tmp_path)
    run = migration_run(info)
    run.stage = MigrationStage.VERIFY
    run.status = MigrationStatus.FAILED
    run.finished_at = datetime.now(UTC)
    saved = []

    async def load_or_create(snapshot_info, environment, approval):
        return run

    async def save(value):
        saved.append(
            (value.stage, value.status, value.finished_at)
        )
        return value

    async def media_handler(snapshot_info, value):
        return {"created": 0, "reused": 1}

    runner = MigrationRunner(
        load_or_create=load_or_create,
        save=save,
        stage_handlers={MigrationStage.MEDIA: media_handler},
    )

    resumed = await runner.run(
        info,
        "staging",
        until_stage="media",
    )

    assert resumed.stage is MigrationStage.MEDIA
    assert resumed.status is MigrationStatus.RUNNING
    assert resumed.finished_at is None
    assert saved == [
        (MigrationStage.MEDIA, MigrationStatus.RUNNING, None)
    ]


@pytest.mark.asyncio
async def test_completed_run_rechecks_idempotency_without_losing_first_pass(
    tmp_path,
):
    info = snapshot(tmp_path)
    run = migration_run(info)
    run.stage = MigrationStage.VERIFY
    run.status = MigrationStatus.COMPLETED
    run.finished_at = datetime.now(UTC)
    run.counters_json = {
        "catalog": {"created": 3},
        "verify": {"passed": True},
    }
    calls = []

    async def load_or_create(snapshot_info, environment, approval):
        return run

    async def save(value):
        return value

    def handler(stage):
        async def execute(snapshot_info, value):
            calls.append(stage.value)
            if stage is MigrationStage.VERIFY:
                return VerificationReport(
                    passed=value.counters_json["idempotency_created"] == 0,
                    gates=[],
                )
            return {"created": 0, "reused": 1}

        return execute

    runner = MigrationRunner(
        load_or_create=load_or_create,
        save=save,
        stage_handlers={
            definition.stage: handler(definition.stage)
            for definition in STAGES
        },
    )

    checked = await runner.run(info, "staging")

    assert calls == [definition.stage.value for definition in STAGES]
    assert checked.status is MigrationStatus.COMPLETED
    assert checked.counters_json["catalog"]["created"] == 3
    assert checked.counters_json["idempotency_created"] == 0
    assert checked.counters_json["idempotency"]["catalog"] == {
        "created": 0,
        "reused": 1,
    }
    assert checked.counters_json["idempotency"]["verify"]["passed"] is True


@pytest.mark.asyncio
async def test_failed_idempotency_verify_resumes_without_overwriting_first_pass(
    tmp_path,
):
    info = snapshot(tmp_path)
    run = migration_run(info)
    run.stage = MigrationStage.VERIFY
    run.status = MigrationStatus.COMPLETED
    run.finished_at = datetime.now(UTC)
    run.counters_json = {
        "catalog": {"created": 3},
        "media": {"created": 2},
        "verify": {"passed": True},
    }
    calls = []
    verify_attempts = 0

    async def load_or_create(snapshot_info, environment, approval):
        return run

    async def save(value):
        return value

    def handler(stage):
        async def execute(snapshot_info, value):
            nonlocal verify_attempts
            calls.append(stage.value)
            if stage is MigrationStage.VERIFY:
                verify_attempts += 1
                return VerificationReport(
                    passed=verify_attempts == 2,
                    gates=[],
                )
            return {"created": 0, "reused": 1}

        return execute

    runner = MigrationRunner(
        load_or_create=load_or_create,
        save=save,
        stage_handlers={
            definition.stage: handler(definition.stage)
            for definition in STAGES
        },
    )

    failed_check = await runner.run(info, "staging")
    assert failed_check.status is MigrationStatus.FAILED

    resumed_check = await runner.run(info, "staging")

    assert calls == [
        *[definition.stage.value for definition in STAGES],
        "media",
        "verify",
    ]
    assert resumed_check.status is MigrationStatus.COMPLETED
    assert resumed_check.counters_json["catalog"] == {"created": 3}
    assert resumed_check.counters_json["media"] == {"created": 2}
    assert resumed_check.counters_json["verify"] == {"passed": True}
    assert resumed_check.counters_json["idempotency_created"] == 0
    assert resumed_check.counters_json["idempotency"]["media"] == {
        "created": 0,
        "reused": 1,
    }
    assert (
        resumed_check.counters_json["idempotency"]["verify"]["passed"]
        is True
    )
    assert "idempotency_in_progress" not in resumed_check.counters_json


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
