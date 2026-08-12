from importlib.util import module_from_spec, spec_from_file_location
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.legacy_migration.late_domains_v9 import _validate_run
from app.legacy_migration.model import (
    MigrationEnvironment,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
)
from app.legacy_migration.runner_v9 import MIGRATION_SCHEMA_VERSION


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "backend/migrations/versions/0042_real_business_subscriptions.py"
)
STAGING_SCRIPT = (
    ROOT / "scripts/Koprik-Phase3C-Complete-Cabinet-Staging-V9.ps1"
)
VERIFIED_SCRIPT = (
    ROOT
    / "scripts/Koprik-Phase3C-Complete-Cabinet-Staging-V9-Verified.ps1"
)


def _migration():
    spec = spec_from_file_location("real_business_subscriptions", MIGRATION)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_v9_has_a_new_schema_version_and_subscription_legacy_unique_key():
    assert MIGRATION_SCHEMA_VERSION == "0009_phase3c_real_subscriptions_v1"

    migration = _migration()
    source = MIGRATION.read_text(encoding="utf-8")
    assert migration.revision == "0042_real_business_subscriptions"
    assert migration.down_revision == "0041_taxi_driver_domain"
    assert "uq_business_subscriptions_legacy" in source
    assert "legacy_source_id IS NOT NULL" in source


def test_v9_late_import_cannot_reuse_a_v8_run():
    run = MigrationRun(
        id=44,
        source_database_sha256="source-sha",
        media_manifest_sha256="manifest-sha",
        schema_version="0008_phase3c_taxi_v1",
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.VERIFY,
        status=MigrationStatus.COMPLETED,
        counters_json={"verify": {"passed": True}},
        error_count=0,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )

    with pytest.raises(RuntimeError, match="schema_version_mismatch"):
        _validate_run(
            run,
            snapshot_sha256="source-sha",
            manifest_sha256="manifest-sha",
        )

    run.schema_version = MIGRATION_SCHEMA_VERSION
    _validate_run(
        run,
        snapshot_sha256="source-sha",
        manifest_sha256="manifest-sha",
    )


def test_v9_packaged_commands_use_v9_runner_and_late_import():
    pyproject = (ROOT / "backend/pyproject.toml").read_text(encoding="utf-8")

    assert 'koprik-migrate-legacy = "app.legacy_migration.cli_v9:main"' in pyproject
    assert (
        'koprik-migrate-complete-cabinets = '
        '"app.legacy_migration.cli_v9:main"'
    ) in pyproject
    assert (
        'koprik-migrate-late-domains = '
        '"app.legacy_migration.late_domains_v9:main"'
    ) in pyproject


def test_v9_rollout_orders_base_upgrade_late_import_and_exact_gate():
    script = STAGING_SCRIPT.read_text(encoding="utf-8")

    assert 'EXPECTED_SCHEMA="0009_phase3c_real_subscriptions_v1"' in script
    assert 'EXPECTED_INITIAL_HEAD="0005_profile_cabinet_parity"' in script
    assert 'EXPECTED_FINAL_HEAD="0042_real_business_subscriptions"' in script
    source_gate = script.index("REAL_BUSINESS_SUBSCRIPTIONS_SOURCE_OK")
    first_target_write = script.index("ALTER TABLE user_profiles ADD COLUMN")
    first_run = script.index("run-1-base.json")
    schema_upgrade = script.index("alembic upgrade head", first_run)
    completed_run = script.index("run-1-complete.json", schema_upgrade)
    late_import = script.index("koprik-migrate-late-domains", completed_run)
    subscription_gate = script.index(
        "REAL_BUSINESS_SUBSCRIPTIONS_OK",
        late_import,
    )
    second_run = script.index("run-2.json", subscription_gate)

    assert (
        source_gate
        < first_target_write
        < first_run
        < schema_upgrade
        < completed_run
        < late_import
        < subscription_gate
        < second_run
    )
    assert "EXPECTED_LEGACY_IDS" in script
    assert "ACTUAL_LEGACY_IDS" in script
    assert "Production migration was not started." in script


def test_verified_v9_wrapper_uses_v9_profile_media_gate():
    script = VERIFIED_SCRIPT.read_text(encoding="utf-8")

    assert "Koprik-Phase3C-Complete-Cabinet-Staging-V9.ps1" in script
    assert "app.legacy_migration.profile_media_verify_v9" in script
    assert 'report["schema_version"] == "0009_phase3c_real_subscriptions_v1"' in script
    assert "PHASE3C_V9_VERIFIED_COMPLETE" in script
    assert "Production migration was not started." in script
