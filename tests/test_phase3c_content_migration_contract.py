from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def class_block(text: str, class_name: str, next_class: str | None) -> str:
    block = text.split(f"class {class_name}", maxsplit=1)[1]
    return block.split(f"class {next_class}", maxsplit=1)[0] if next_class else block


def test_phase3c_contract_keeps_legacy_and_separates_listing_from_ad():
    legacy = source("static/index.html")
    listing = source("backend/app/listings/model.py")
    advertisement = source("backend/app/advertisements/model.py")

    assert "<!-- BUILD: v1656 -->" in legacy
    assert len(legacy.splitlines()) == 14_091
    assert '__tablename__ = "listings"' in listing
    assert "price_text" in listing
    assert '__tablename__ = "advertisements"' in advertisement
    assert "daily_start" in advertisement
    assert "targets_json" in advertisement


def test_public_contract_never_exposes_private_identifiers():
    backend_blocks = [
        class_block(
            source("backend/app/catalog/schemas.py"),
            "PublicCatalogItem",
            "PublicCatalogResponse",
        ),
        class_block(
            source("backend/app/advertisements/schemas.py"),
            "PublicAdvertisement",
            None,
        ),
        class_block(
            source("backend/app/public_discovery/schemas.py"),
            "PublicSearchItem",
            "PublicSearchResponse",
        ),
    ]
    frontend = source("frontend/src/api/types.ts")
    frontend_public = frontend.split(
        "export type PublicResultKind", maxsplit=1
    )[1]
    public_sources = "\n".join([*backend_blocks, frontend_public])

    for forbidden in (
        "password_hash",
        "telegram_user_id",
        "business_account_id",
        "image_object_key",
        "desktop_image_object_key",
        "legacy_id",
    ):
        assert forbidden not in public_sources


def test_migration_stage_flags_cache_and_report_guards_are_fixed():
    migration = source(
        "backend/migrations/versions/0003_phase3c_content.py"
    )
    runner = source("backend/app/legacy_migration/runner.py")
    config = source("backend/app/core/config.py")
    discovery = source("backend/app/public_discovery/service.py")
    report = source("backend/app/legacy_migration/report.py")

    assert 'revision = "0003_phase3c_content"' in migration
    positions = [
        runner.index(f"MigrationStage.{stage}")
        for stage in (
            "INVENTORY",
            "ACCOUNTS",
            "BUSINESSES",
            "CATALOG",
            "LISTINGS",
            "ADVERTISEMENTS",
            "MEDIA",
            "VERIFY",
        )
    ]
    assert positions == sorted(positions)
    assert "listings_enabled: bool = False" in config
    assert "phase3c_public_enabled: bool = False" in config
    assert 'public:search:v3:' in discovery
    assert "CatalogCacheEpoch" in discovery
    for forbidden in ("pass_plain", "token", "source_reference"):
        assert f'"{forbidden}"' in report


def test_frontend_backend_public_field_names_stay_in_parity():
    backend = source("backend/app/catalog/schemas.py")
    frontend = source("frontend/src/api/types.ts")
    for field in (
        "kind",
        "public_id",
        "name",
        "price_text",
        "note",
        "owner_state",
        "owner_public_id",
        "owner_name",
        "owner_label",
        "direction",
        "activity_type",
        "region",
        "district",
        "mahalla",
        "image_url",
        "can_order",
        "can_chat",
    ):
        assert f"{field}:" in backend
        assert f"{field}:" in frontend


def test_maintenance_verifier_and_runbooks_cover_safe_cutover():
    maintenance = source("frontend/public/maintenance.html")
    staging = source("docs/deploy-phase3c-staging.md")
    production = source("docs/deploy-phase3c-production.md")
    verifier = ROOT / "scripts/verify_phase3c.py"

    assert "Texnik ishlar olib borilmoqda" in maintenance
    assert "/api/" not in maintenance
    assert verifier.is_file()
    for expected in (
        "0003_phase3c_content",
        "created=0",
        "failed=0",
        "KOPRIK_PHASE3C_PUBLIC_ENABLED=true",
        "approved staging run ID",
    ):
        assert expected in staging
    for expected in (
        "/maintenance.html",
        "approved staging run",
        "maintenance",
        "rollback",
        "monolith",
        "do not delete",
        "qayta kir",
    ):
        assert expected.lower() in production.lower()


def test_repository_verifier_passes():
    result = subprocess.run(
        [sys.executable, "scripts/verify_phase3c.py", "--static-only"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 3C static contract: PASS" in result.stdout


def test_legacy_verifier_uses_an_isolated_database_per_run():
    verifier = source("scripts/verify_phase1.py")

    assert "TemporaryDirectory" in verifier
    assert 'test_env["DB_PATH"]' in verifier
    assert 'test_env["UPLOAD_DIR"]' in verifier


def test_phase3b_verifier_references_an_existing_contract():
    verifier = source("scripts/verify_phase3b.py")

    assert "tests/test_phase3_public_discovery_contract.py" in verifier
    assert "tests/test_phase3b_public_shell.py" not in verifier
