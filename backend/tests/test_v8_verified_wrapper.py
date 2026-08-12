from pathlib import Path


def test_verified_v8_wrapper_enforces_profile_media_gate_after_base_run():
    script = (
        Path(__file__).parents[2]
        / "scripts/Koprik-Phase3C-Complete-Cabinet-Staging-V8-Verified.ps1"
    ).read_text(encoding="utf-8")

    assert "MIGRATION_MODE=FRESH_CURRENT_TYPED_CABINETS_WITH_PROFILE_MEDIA_GATE" in script
    base_run = script.index("& $BaseScript @RunParams")
    verifier = script.index("app.legacy_migration.profile_media_verify_v8")
    verified_complete = script.index("PHASE3C_V8_VERIFIED_COMPLETE")

    assert base_run < verifier < verified_complete
    assert '--environment staging' in script
    assert '--snapshot "$SNAPSHOT"' in script
    assert '--run-id "$RUN_ID"' in script
    assert 'report["schema_version"] == "0008_phase3c_taxi_v1"' in script
    assert 'report["verification"]["passed"] is True' in script
    assert "STAGING_V8_PROFILE_MEDIA_GATE_FAILED" in script
    assert "Production migration was not started." in script


def test_verified_v8_wrapper_preserves_dry_run_without_profile_media_check():
    script = (
        Path(__file__).parents[2]
        / "scripts/Koprik-Phase3C-Complete-Cabinet-Staging-V8-Verified.ps1"
    ).read_text(encoding="utf-8")

    base_run = script.index("& $BaseScript @RunParams")
    dry_run_exit = script.index("VERIFIED_WRAPPER_DRY_RUN_COMPLETE")
    verifier = script.index("app.legacy_migration.profile_media_verify_v8")

    assert base_run < dry_run_exit < verifier
    assert 'if (-not $Execute.IsPresent)' in script
