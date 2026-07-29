from datetime import UTC, datetime
import json

import pytest

from app.legacy_migration.model import (
    MigrationEnvironment,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
)
from app.legacy_migration.report import (
    UnsafeReportData,
    build_report,
    render_json,
    render_markdown,
)
from app.legacy_migration.verify import GateResult, VerificationReport


def run():
    return MigrationRun(
        id=42,
        source_database_sha256="a" * 64,
        media_manifest_sha256="b" * 64,
        schema_version="0003_phase3c_content",
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.VERIFY,
        status=MigrationStatus.COMPLETED,
        counters_json={"catalog": {"created": 2}},
        error_count=0,
        started_at=datetime(2026, 7, 29, tzinfo=UTC),
        finished_at=datetime(2026, 7, 29, 1, tzinfo=UTC),
    )


def test_report_contains_only_safe_codes_and_counts():
    verification = VerificationReport(
        passed=True,
        gates=[GateResult("media_failed", True, 0, 0)],
    )
    report = build_report(
        run(),
        issues=[
            {
                "entity_type": "catalog_item",
                "legacy_id": 8,
                "issue_code": "catalog.required.name",
            }
        ],
        verification=verification,
    )

    encoded = render_json(report)
    markdown = render_markdown(report)

    assert json.loads(encoded)["run_id"] == 42
    assert "catalog.required.name" in encoded
    assert "media_failed" in markdown
    assert "login" not in encoded


@pytest.mark.parametrize(
    "unsafe",
    [
        {"login": "admin"},
        {"details": {"pass_plain": "secret"}},
        {"token": "secret"},
        {"source_reference": "/srv/uploads/private.png"},
    ],
)
def test_report_rejects_private_fields(unsafe):
    with pytest.raises(UnsafeReportData, match="unsafe_report_key"):
        render_json(unsafe)

