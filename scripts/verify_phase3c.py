from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SystemExit(f"Phase 3C contract failed: {code}")


def run_static_checks() -> None:
    legacy = text("static/index.html")
    require("<!-- BUILD: v1656 -->" in legacy, "legacy_build_changed")
    require(len(legacy.splitlines()) == 14_091, "legacy_line_count_changed")

    migration = text("backend/migrations/versions/0003_phase3c_content.py")
    require(
        'revision = "0003_phase3c_content"' in migration,
        "migration_revision_missing",
    )
    config = text("backend/app/core/config.py")
    require(
        "listings_enabled: bool = False" in config,
        "listings_enabled_by_default",
    )
    require(
        "phase3c_public_enabled: bool = False" in config,
        "phase3c_public_enabled_by_default",
    )

    runner = text("backend/app/legacy_migration/runner.py")
    stages = (
        "INVENTORY",
        "ACCOUNTS",
        "BUSINESSES",
        "CATALOG",
        "LISTINGS",
        "ADVERTISEMENTS",
        "MEDIA",
        "VERIFY",
    )
    positions = [runner.index(f"MigrationStage.{stage}") for stage in stages]
    require(positions == sorted(positions), "migration_stage_order_changed")

    catalog = text("backend/app/catalog/schemas.py")
    advertisement = text("backend/app/advertisements/schemas.py")
    discovery = text("backend/app/public_discovery/schemas.py")
    public_contract = "\n".join((catalog, advertisement, discovery))
    for forbidden in (
        "password_hash",
        "telegram_user_id",
        "business_account_id",
        "image_object_key",
        "legacy_id",
    ):
        require(
            forbidden not in public_contract,
            f"public_field_leak:{forbidden}",
        )

    require(
        "public:search:v3:" in text(
            "backend/app/public_discovery/service.py"
        ),
        "search_cache_version_missing",
    )
    require(
        "CatalogCacheEpoch" in text(
            "backend/app/public_discovery/service.py"
        ),
        "catalog_cache_epoch_missing",
    )
    maintenance = text("frontend/public/maintenance.html")
    require(
        "Texnik ishlar olib borilmoqda" in maintenance,
        "maintenance_page_missing",
    )
    require("/api/" not in maintenance, "maintenance_page_calls_api")
    require(
        (ROOT / "docs/deploy-phase3c-staging.md").is_file(),
        "staging_runbook_missing",
    )
    require(
        (ROOT / "docs/deploy-phase3c-production.md").is_file(),
        "production_runbook_missing",
    )
    print("Phase 3C static contract: PASS")


def run(command: list[str], cwd: Path = ROOT) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--static-only", action="store_true")
    args = parser.parse_args()
    run_static_checks()
    if args.static_only:
        return 0

    run([sys.executable, "-m", "pytest", "tests", "-q"], BACKEND)
    run(["npm", "test"], FRONTEND)
    run(["npm", "run", "build"], FRONTEND)
    run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_phase3c_content_migration_contract.py",
            "-q",
        ]
    )
    print("Phase 3C: automated gate PASS")
    print("BUILD: v1656")
    print("static/index.html: 14091 qator")
    print("Production migration: bajarilmadi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
