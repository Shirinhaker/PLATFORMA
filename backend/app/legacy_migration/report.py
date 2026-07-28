from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from enum import Enum
import json
from typing import Any

from app.legacy_migration.model import MigrationRun
from app.legacy_migration.verify import VerificationReport


FORBIDDEN_REPORT_KEYS = {
    "name",
    "phone",
    "login",
    "telegram_user_id",
    "tg_id",
    "password",
    "pass_hash",
    "pass_plain",
    "token",
    "source_reference",
    "object_url",
}


class UnsafeReportData(ValueError):
    pass


def build_report(
    run: MigrationRun,
    *,
    issues: list[dict[str, Any]],
    verification: VerificationReport,
) -> dict[str, Any]:
    safe_issues = [
        {
            "entity_type": issue["entity_type"],
            "legacy_id": issue.get("legacy_id"),
            "issue_code": issue["issue_code"],
        }
        for issue in issues
    ]
    report = {
        "run_id": run.id,
        "source_database_sha256": run.source_database_sha256,
        "media_manifest_sha256": run.media_manifest_sha256,
        "schema_version": run.schema_version,
        "environment": run.environment,
        "stage": run.stage,
        "status": run.status,
        "counters": run.counters_json,
        "error_count": run.error_count,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "issues": safe_issues,
        "verification": asdict(verification),
    }
    _validate_safe(report)
    return report


def render_json(report: dict[str, Any]) -> str:
    _validate_safe(report)
    return json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=_json_default,
    )


def render_markdown(report: dict[str, Any]) -> str:
    _validate_safe(report)
    verification = report.get("verification") or {}
    lines = [
        f"# Phase 3C migration run {report.get('run_id', '')}",
        "",
        f"- Environment: {_plain(report.get('environment'))}",
        f"- Stage: {_plain(report.get('stage'))}",
        f"- Status: {_plain(report.get('status'))}",
        f"- Errors: {report.get('error_count', 0)}",
        "",
        "## Gates",
        "",
    ]
    for gate in verification.get("gates", []):
        mark = "PASS" if gate.get("passed") else "FAIL"
        lines.append(f"- {mark}: {gate.get('code', '')}")
    lines.extend(["", "## Issues", ""])
    for issue in report.get("issues", []):
        lines.append(
            f"- {issue.get('entity_type')} #{issue.get('legacy_id')}: "
            f"{issue.get('issue_code')}"
        )
    return "\n".join(lines).rstrip() + "\n"


def _validate_safe(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_REPORT_KEYS:
                raise UnsafeReportData(
                    f"unsafe_report_key:{normalized}"
                )
            _validate_safe(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _validate_safe(child)


def _json_default(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Unsupported report value: {type(value).__name__}")


def _plain(value: object) -> object:
    return value.value if isinstance(value, Enum) else value

