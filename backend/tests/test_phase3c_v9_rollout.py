from importlib.util import module_from_spec, spec_from_file_location
from datetime import UTC, datetime
from pathlib import Path
import subprocess

import pytest

from app.legacy_migration.late_domains_v9 import _validate_run
from app.legacy_migration.model import (
    MigrationEnvironment,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
)
from app.legacy_migration.runner_v9 import MIGRATION_SCHEMA_VERSION
from app.legacy_migration.production_guard_v9 import (
    validate_promotion_media_rows,
)
from app.legacy_migration.model import MediaMigrationState
from types import SimpleNamespace


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
PRODUCTION_SCRIPT = (
    ROOT
    / "scripts/Koprik-Phase3C-Promote-Cabinet-Production-V9.ps1"
)
PRODUCTION_RUNBOOK = ROOT / "docs/deploy-phase3c-production.md"
WRITE_FREEZE_RUNBOOK = ROOT / "docs/phase3c-v9-final-write-freeze.md"


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


def test_v9_production_promotion_requires_exact_verified_candidate():
    script = PRODUCTION_SCRIPT.read_text(encoding="utf-8")

    assert 'Write-Host "SCRIPT_VERSION=9"' in script
    assert "MIGRATION_MODE=PROMOTE_VERIFIED_V9_CANDIDATE" in script
    assert '$ExpectedSchema = "0009_phase3c_real_subscriptions_v1"' in script
    assert '$ExpectedHead = "0042_real_business_subscriptions"' in script
    assert "koprik-phase3c-v9-" in script
    assert "app.legacy_migration.runner_v9" in script
    assert "app.legacy_migration.profile_media_verify_v9" in script
    assert "PROFILE_MEDIA_V9_VERIFY_OK" in script
    assert "REAL_BUSINESS_SUBSCRIPTIONS_PRODUCTION_GUARD_OK" in script
    assert "validate_media_for_promotion" in script
    assert "EXPIRED_STORY_MEDIA_MISSING" in script
    assert "terminal_media = copied + media_guard.expired_story_missing" in script
    assert 'export KOPRIK_LEGACY_MEDIA_ROOTS="$MEDIA"' in script
    assert 'approved_media_root_not_found' in script
    assert "candidate_environment_must_remain_staging_before_cutover" in script
    assert "phase3c_public_flag_must_be_disabled" in script
    assert "candidate_database_not_at_current_head" in script
    assert "approved_staging_run_not_found" in script
    assert "approved_staging_verification_failed" in script
    assert "PRODUCTION_V9_BACKUP_CONFIRMATION_REQUIRED" in script
    assert "PRODUCTION_V9_MAINTENANCE_CONFIRMATION_REQUIRED" in script
    assert "PRODUCTION_V9_SOURCE_WRITES_STOPPED_CONFIRMATION_REQUIRED" in script
    assert "--environment production" in script
    assert "--confirm-environment production" in script
    assert "--confirm-snapshot-sha256" in script
    assert "--maintenance-enabled" in script
    assert "--approved-staging-run-id" in script
    assert "PHASE3C_V9_PRODUCTION_PROMOTION_COMPLETE" in script
    assert "TRAFFIC_NOT_CHANGED=1" in script
    assert "alembic upgrade head" not in script
    profile_gate = script.index("PROFILE_MEDIA_V9_VERIFY_OK")
    subscription_gate = script.index(
        "REAL_BUSINESS_SUBSCRIPTIONS_PRODUCTION_GUARD_OK"
    )
    final_guard = script.index("PRODUCTION_V9_PROMOTION_GUARD_OK")
    production_write = script.index("koprik-migrate-legacy run")
    assert profile_gate < subscription_gate < final_guard < production_write


def test_v9_promotion_allows_only_expired_failed_story_media():
    now = datetime(2026, 8, 13, tzinfo=UTC)
    rows = [
        SimpleNamespace(
            id=1,
            entity_type="catalog_item",
            legacy_id=11,
            state=MediaMigrationState.COPIED,
        ),
        SimpleNamespace(
            id=2,
            entity_type="story",
            legacy_id=21,
            state=MediaMigrationState.MISSING,
        ),
    ]
    stories = {
        21: SimpleNamespace(
            migration_run_id=7,
            status="failed",
            expires_at=datetime(2026, 8, 12, tzinfo=UTC),
            deleted_at=None,
        )
    }

    result = validate_promotion_media_rows(
        rows,
        stories,
        {21},
        run_id=7,
        now=now,
    )

    assert result.copied == 1
    assert result.expired_story_missing == 1


@pytest.mark.parametrize(
    ("row", "story", "issues", "error"),
    [
        (
            SimpleNamespace(
                id=2,
                entity_type="catalog_item",
                legacy_id=21,
                state=MediaMigrationState.MISSING,
            ),
            None,
            set(),
            "promotion_non_story_media_missing",
        ),
        (
            SimpleNamespace(
                id=2,
                entity_type="story",
                legacy_id=21,
                state=MediaMigrationState.MISSING,
            ),
            SimpleNamespace(
                migration_run_id=7,
                status="failed",
                expires_at=datetime(2026, 8, 14, tzinfo=UTC),
                deleted_at=None,
            ),
            {21},
            "promotion_active_story_media_missing",
        ),
        (
            SimpleNamespace(
                id=2,
                entity_type="story",
                legacy_id=21,
                state=MediaMigrationState.MISSING,
            ),
            SimpleNamespace(
                migration_run_id=7,
                status="failed",
                expires_at=datetime(2026, 8, 12, tzinfo=UTC),
                deleted_at=None,
            ),
            set(),
            "promotion_missing_story_issue_not_found",
        ),
    ],
)
def test_v9_promotion_rejects_unsafe_missing_media(
    row,
    story,
    issues,
    error,
):
    with pytest.raises(RuntimeError, match=error):
        validate_promotion_media_rows(
            [row],
            {21: story} if story is not None else {},
            issues,
            run_id=7,
            now=datetime(2026, 8, 13, tzinfo=UTC),
        )


def test_v9_production_embedded_bash_blocks_parse():
    script = PRODUCTION_SCRIPT.read_text(encoding="utf-8")

    for variable in ("PreflightScript", "ExecuteScript"):
        marker = f"${variable} = @'\n"
        start = script.index(marker) + len(marker)
        end = script.index("\n'@", start)
        result = subprocess.run(
            ["bash", "-n"],
            input=script[start:end],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def test_production_runbooks_point_to_v9_only():
    runbook = PRODUCTION_RUNBOOK.read_text(encoding="utf-8")
    freeze = WRITE_FREEZE_RUNBOOK.read_text(encoding="utf-8")

    assert "Phase 3C V9 production cutover" in runbook
    assert "Koprik-Phase3C-Complete-Cabinet-Staging-V9-Verified.ps1" in runbook
    assert "Koprik-Phase3C-Promote-Cabinet-Production-V9.ps1" in runbook
    assert "0009_phase3c_real_subscriptions_v1" in runbook
    assert "0042_real_business_subscriptions" in runbook
    assert "Phase 3C V9 final write-freeze" in freeze
    assert "V9 final staging rehearsal" in freeze
    for obsolete_reference in (
        "Complete-Cabinet-Staging-V8",
        "Promote-Cabinet-Production-V8",
        "koprik-phase3c-v8-",
        "V8 snapshot",
        "V8 staging rehearsal",
    ):
        assert obsolete_reference not in runbook
    assert "V8" not in freeze
