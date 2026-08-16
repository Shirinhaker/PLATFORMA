from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from app.core.config import Settings
from app.db.session import Database
from app.legacy_migration.model import (
    MigrationEnvironment,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
)
from app.legacy_migration.profile_media_v8 import migrate_profile_images
from app.legacy_migration.profile_parity_v7 import import_late_typed_domains
from app.legacy_migration.real_source_v9 import open_real_snapshot
from app.legacy_migration.runner_v9 import MIGRATION_SCHEMA_VERSION
from app.legacy_migration.source import file_sha256
from app.media.storage import build_r2_storage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="koprik-migrate-late-domains")
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument(
        "--environment",
        required=True,
        choices=("staging",),
    )
    return parser


async def run(*, snapshot: Path, run_id: int, environment: str) -> int:
    settings = Settings()
    if environment != "staging" or settings.environment != "staging":
        raise RuntimeError("late_domains_environment_is_not_staging")
    if settings.phase3c_public_enabled:
        raise RuntimeError("late_domains_public_flag_must_be_disabled")

    snapshot_path = snapshot.resolve(strict=True)
    manifest_path = snapshot_path.parent / "media-manifest.json"
    snapshot_sha256 = file_sha256(snapshot_path)
    manifest_sha256 = file_sha256(manifest_path)

    database = Database(settings.database_url)
    storage = build_r2_storage(settings)
    await database.start()
    try:
        async with database.session() as session, session.begin():
            migration_run = await session.get(MigrationRun, run_id)
            _validate_run(
                migration_run,
                snapshot_sha256=snapshot_sha256,
                manifest_sha256=manifest_sha256,
            )
            source = open_real_snapshot(snapshot_path)
            try:
                typed_result = await import_late_typed_domains(
                    session,
                    source,
                    migration_run,
                )
                profile_media_result = await migrate_profile_images(
                    session,
                    source,
                    storage,
                    migration_run,
                )
            finally:
                source.close()

            counters = dict(migration_run.counters_json)
            counters["late_typed_domains"] = asdict(typed_result)
            counters["profile_media"] = asdict(profile_media_result)
            migration_run.counters_json = counters
            await session.flush()
    finally:
        await database.stop()

    print(
        json.dumps(
            {
                "environment": environment,
                "run_id": run_id,
                "schema_version": MIGRATION_SCHEMA_VERSION,
                "late_typed_domains": asdict(typed_result),
                "profile_media": asdict(profile_media_result),
            },
            sort_keys=True,
        )
    )
    return 0


def _validate_run(
    migration_run: MigrationRun | None,
    *,
    snapshot_sha256: str,
    manifest_sha256: str,
) -> None:
    if migration_run is None:
        raise RuntimeError("late_domains_migration_run_not_found")
    if migration_run.environment is not MigrationEnvironment.STAGING:
        raise RuntimeError("late_domains_run_is_not_staging")
    if migration_run.schema_version != MIGRATION_SCHEMA_VERSION:
        raise RuntimeError("late_domains_schema_version_mismatch")
    if migration_run.source_database_sha256 != snapshot_sha256:
        raise RuntimeError("late_domains_snapshot_sha256_mismatch")
    if migration_run.media_manifest_sha256 != manifest_sha256:
        raise RuntimeError("late_domains_manifest_sha256_mismatch")
    if (
        migration_run.status is not MigrationStatus.COMPLETED
        or migration_run.stage is not MigrationStage.VERIFY
        or not (migration_run.counters_json.get("verify") or {}).get("passed")
    ):
        raise RuntimeError("late_domains_base_run_not_verified")


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(
        run(
            snapshot=args.snapshot,
            run_id=args.run_id,
            environment=args.environment,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
