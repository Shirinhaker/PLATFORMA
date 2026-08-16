from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path

from app.core.config import Settings
from app.db.session import Database
from app.legacy_migration.late_domains_v9 import _validate_run
from app.legacy_migration.model import MigrationRun
from app.legacy_migration.profile_media_verify_v8 import (
    expected_profile_media,
    verify_profile_media_counter,
)
from app.legacy_migration.source import file_sha256


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="koprik-verify-profile-media-v9")
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
        raise RuntimeError("profile_media_verify_environment_is_not_staging")
    if settings.phase3c_public_enabled:
        raise RuntimeError("profile_media_verify_public_flag_must_be_disabled")

    snapshot_path = snapshot.resolve(strict=True)
    manifest_path = snapshot_path.parent / "media-manifest.json"
    snapshot_sha256 = file_sha256(snapshot_path)
    manifest_sha256 = file_sha256(manifest_path)

    source = sqlite3.connect(
        f"file:{snapshot_path}?mode=ro&immutable=1",
        uri=True,
    )
    try:
        expectation = expected_profile_media(source)
    finally:
        source.close()

    database = Database(settings.database_url)
    await database.start()
    try:
        async with database.session() as session:
            migration_run = await session.get(MigrationRun, run_id)
            _validate_run(
                migration_run,
                snapshot_sha256=snapshot_sha256,
                manifest_sha256=manifest_sha256,
            )
            if migration_run is None:
                raise RuntimeError("profile_media_verify_run_not_found")
            values = verify_profile_media_counter(migration_run, expectation)
    finally:
        await database.stop()

    payload = {
        "environment": environment,
        "run_id": run_id,
        "expected": expectation.total,
        "expected_users": expectation.users,
        "expected_businesses": expectation.businesses,
        **values,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "PROFILE_MEDIA_V9_VERIFY_OK "
        f"RUN_ID={run_id} EXPECTED={expectation.total} "
        f"MIGRATED={values['migrated']} USERS={expectation.users} "
        f"BUSINESSES={expectation.businesses}"
    )
    return 0


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
