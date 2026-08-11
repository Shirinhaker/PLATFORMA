from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.legacy_migration.late_domains_v8 import _validate_run
from app.legacy_migration.model import (
    MigrationEnvironment,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
)
from app.legacy_migration.profile_parity_v7 import (
    reconcile_accounts,
    reconcile_businesses,
)
from app.legacy_migration.reconcile import StageResult
from app.legacy_migration.runner_v6 import MIGRATION_SCHEMA_VERSION


class Session:
    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_base_import_defers_typed_domains_until_their_tables_exist(
    monkeypatch,
):
    async def base(*_args):
        return StageResult(created=2)

    async def enrich(*_args):
        return None

    async def target_tables_missing(*_args):
        return False

    async def must_not_run(*_args):
        raise AssertionError("late typed import bazaviy 0005 bosqichida ishlamasin")

    module = "app.legacy_migration.profile_parity_v7"
    monkeypatch.setattr(f"{module}.reconcile_accounts_v6", base)
    monkeypatch.setattr(f"{module}.reconcile_businesses_v6", base)
    monkeypatch.setattr(f"{module}.enrich_user_cabinets", enrich)
    monkeypatch.setattr(f"{module}.enrich_business_cabinets", enrich)
    monkeypatch.setattr(f"{module}._target_tables_exist", target_tables_missing)
    monkeypatch.setattr(f"{module}.import_taxi_domain", must_not_run)
    monkeypatch.setattr(f"{module}.import_ai_chat_history", must_not_run)

    accounts = await reconcile_accounts(Session(), object(), object())
    businesses = await reconcile_businesses(Session(), object(), object())

    assert accounts == StageResult(created=2)
    assert businesses == StageResult(created=2)


def test_late_domain_import_requires_verified_current_staging_run():
    run = MigrationRun(
        id=44,
        source_database_sha256="source-sha",
        media_manifest_sha256="manifest-sha",
        schema_version=MIGRATION_SCHEMA_VERSION,
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.VERIFY,
        status=MigrationStatus.COMPLETED,
        counters_json={"verify": {"passed": True}},
        error_count=0,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )

    _validate_run(
        run,
        snapshot_sha256="source-sha",
        manifest_sha256="manifest-sha",
    )

    run.schema_version = "old-run"
    with pytest.raises(RuntimeError, match="schema_version_mismatch"):
        _validate_run(
            run,
            snapshot_sha256="source-sha",
            manifest_sha256="manifest-sha",
        )


def test_v8_rollout_script_preserves_the_required_order():
    script = (
        Path(__file__).parents[2]
        / "scripts/Koprik-Phase3C-Complete-Cabinet-Staging-V8.ps1"
    ).read_text(encoding="utf-8")

    assert 'EXPECTED_SCHEMA="0008_phase3c_taxi_v1"' in script
    assert 'EXPECTED_INITIAL_HEAD="0005_profile_cabinet_parity"' in script
    assert 'EXPECTED_FINAL_HEAD="0041_taxi_driver_domain"' in script
    first_run = script.index("run-1-base.json")
    schema_upgrade = script.index("alembic upgrade head", first_run)
    completed_run = script.index("run-1-complete.json", schema_upgrade)
    late_import = script.index("koprik-migrate-late-domains", completed_run)
    second_run = script.index("run-2.json", late_import)
    normalization = script.index(
        "app.cabinet_records.cli \\",
        second_run,
    )

    assert (
        first_run
        < schema_upgrade
        < completed_run
        < late_import
        < second_run
        < normalization
    )
