from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path

from sqlalchemy import select

from app.core.config import Settings
from app.db.session import Database
from app.legacy_migration.model import MigrationIssue, MigrationRun
from app.legacy_migration.report import (
    build_report,
    render_json,
    render_markdown,
)
from app.legacy_migration.runner import (
    ProductionApproval,
    build_database_runner,
)
from app.legacy_migration.source import (
    SnapshotInfo,
    create_snapshot,
    file_sha256,
)
from app.legacy_migration.verify import (
    GateResult,
    VerificationReport,
)
from app.media.storage import build_r2_storage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="koprik-migrate-legacy")
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot = subparsers.add_parser("snapshot")
    snapshot.add_argument("--source", required=True, type=Path)
    snapshot.add_argument("--output", required=True, type=Path)
    snapshot.add_argument("--media-root", action="append", type=Path)

    run = subparsers.add_parser("run")
    run.add_argument("--snapshot", required=True, type=Path)
    run.add_argument(
        "--environment",
        required=True,
        choices=("staging", "production"),
    )
    run.add_argument("--until-stage")
    run.add_argument("--confirm-environment")
    run.add_argument("--confirm-snapshot-sha256")
    run.add_argument("--maintenance-enabled", action="store_true")
    run.add_argument("--approved-staging-run-id", type=int)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--run-id", required=True, type=int)

    report = subparsers.add_parser("report")
    report.add_argument("--run-id", required=True, type=int)
    report.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
    )
    return parser


async def _run_command(args) -> int:
    if args.command == "snapshot":
        info = create_snapshot(
            args.source,
            args.output,
            tuple(args.media_root or ()),
        )
        print(
            json.dumps(
                {
                    "database_sha256": info.database_sha256,
                    "manifest_sha256": info.manifest_sha256,
                    "snapshot": str(info.path),
                },
                sort_keys=True,
            )
        )
        return 0

    settings = Settings()
    database = Database(settings.database_url)
    await database.start()
    try:
        if args.command == "run":
            info = _snapshot_info(args.snapshot)
            approval = None
            if args.environment == "production":
                approval = ProductionApproval(
                    typed_environment=args.confirm_environment or "",
                    typed_snapshot_sha256=(
                        args.confirm_snapshot_sha256 or ""
                    ),
                    maintenance_enabled=args.maintenance_enabled,
                    approved_staging_run_id=(
                        args.approved_staging_run_id or 0
                    ),
                )
            runner = build_database_runner(
                database,
                settings,
                build_r2_storage(settings),
            )
            run = await runner.run(
                info,
                args.environment,
                until_stage=args.until_stage,
                approval=approval,
            )
            print(json.dumps({"run_id": run.id, "stage": run.stage.value}))
            return 0 if run.status.value != "failed" else 1
        return await _report_command(database, args)
    finally:
        await database.stop()


async def _report_command(database: Database, args) -> int:
    async with database.session() as session:
        run = await session.get(MigrationRun, args.run_id)
        if run is None:
            raise SystemExit("migration_run_not_found")
        issue_rows = (
            await session.scalars(
                select(MigrationIssue).where(
                    MigrationIssue.migration_run_id == run.id
                )
            )
        ).all()
    verify_payload = run.counters_json.get("verify") or {
        "passed": False,
        "gates": [],
    }
    verification = VerificationReport(
        passed=bool(verify_payload.get("passed")),
        gates=[
            GateResult(**gate)
            for gate in verify_payload.get("gates", [])
        ],
    )
    if args.command == "verify":
        print(json.dumps(asdict(verification), sort_keys=True))
        return 0 if verification.passed else 1
    report = build_report(
        run,
        issues=[
            {
                "entity_type": issue.entity_type,
                "legacy_id": issue.legacy_id,
                "issue_code": issue.issue_code,
            }
            for issue in issue_rows
        ],
        verification=verification,
    )
    renderer = render_markdown if args.format == "markdown" else render_json
    print(renderer(report), end="")
    return 0


def _snapshot_info(path: Path) -> SnapshotInfo:
    snapshot = path.resolve(strict=True)
    manifest = snapshot.parent / "media-manifest.json"
    return SnapshotInfo(
        path=snapshot,
        database_sha256=file_sha256(snapshot),
        manifest_path=manifest,
        manifest_sha256=file_sha256(manifest),
    )


def main() -> None:
    raise SystemExit(asyncio.run(_run_command(build_parser().parse_args())))
