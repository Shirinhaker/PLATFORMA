from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3

from app.core.config import Settings
from app.db.session import Database
from app.legacy_migration.late_domains_v8 import _validate_run
from app.legacy_migration.model import MigrationRun
from app.legacy_migration.source import file_sha256


@dataclass(frozen=True)
class ProfileMediaExpectation:
    total: int
    users: int
    businesses: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="koprik-verify-profile-media-v8")
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument(
        "--environment",
        required=True,
        choices=("staging",),
    )
    return parser


def _table_exists(source: sqlite3.Connection, table: str) -> bool:
    return bool(
        source.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table,),
        ).fetchone()
    )


def expected_profile_media(source: sqlite3.Connection) -> ProfileMediaExpectation:
    required = ("profile_images", "users", "businesses")
    missing = [table for table in required if not _table_exists(source, table)]
    if missing:
        raise RuntimeError(
            "profile_media_source_table_missing:" + ",".join(sorted(missing))
        )

    rows = source.execute(
        """
        SELECT lower(trim(coalesce(p.owner_kind, ''))) AS owner_kind,
               p.owner_id
        FROM profile_images AS p
        WHERE (
            lower(trim(coalesce(p.owner_kind, ''))) = 'user'
            AND EXISTS (
                SELECT 1 FROM users AS u WHERE u.id = p.owner_id
            )
        ) OR (
            lower(trim(coalesce(p.owner_kind, ''))) = 'business'
            AND EXISTS (
                SELECT 1 FROM businesses AS b WHERE b.id = p.owner_id
            )
        )
        ORDER BY owner_kind, p.owner_id
        """
    ).fetchall()
    users = sum(1 for row in rows if str(row[0]) == "user")
    businesses = sum(1 for row in rows if str(row[0]) == "business")
    return ProfileMediaExpectation(
        total=len(rows),
        users=users,
        businesses=businesses,
    )


def verify_profile_media_counter(
    run: MigrationRun,
    expectation: ProfileMediaExpectation,
) -> dict[str, int]:
    counters = run.counters_json.get("profile_media")
    if not isinstance(counters, dict):
        raise RuntimeError("profile_media_counter_missing")

    values = {
        key: int(counters.get(key, 0) or 0)
        for key in ("created", "reused", "updated", "quarantined", "issues")
    }
    if values["quarantined"] != 0 or values["issues"] != 0:
        raise RuntimeError(
            "profile_media_counter_not_clean:"
            f"quarantined={values['quarantined']}:issues={values['issues']}"
        )

    migrated = values["created"] + values["reused"]
    if migrated != expectation.total:
        raise RuntimeError(
            "profile_media_count_mismatch:"
            f"expected={expectation.total}:migrated={migrated}"
        )
    values["migrated"] = migrated
    return values


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
        "PROFILE_MEDIA_V8_VERIFY_OK "
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
