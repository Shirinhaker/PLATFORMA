from datetime import UTC, datetime
import sqlite3

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.advertisements.model import Advertisement
from app.catalog.model import CatalogItem
from app.db.base import Base
from app.legacy_migration.model import (
    LegacyIdMap,
    MediaMigration,
    MediaMigrationState,
    MigrationEnvironment,
    MigrationIssue,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
)
from app.listings.model import Listing
from app.legacy_migration.verify import (
    VerificationInput,
    evaluate_gates,
    verify_migration,
)


def valid_input(**changes):
    values = {
        "source_rows": 20,
        "mapped_rows": 20,
        "source_catalog_kinds": {"product": 5, "service": 3},
        "target_catalog_kinds": {"product": 5, "service": 3},
        "source_listings": 4,
        "target_listings": 4,
        "source_advertisements": 2,
        "target_advertisements": 2,
        "broken_foreign_keys": 0,
        "identity_conflicts": 0,
        "source_media_references": 6,
        "media_copied": 4,
        "media_missing": 1,
        "media_invalid": 1,
        "media_failed": 0,
        "copied_media_unverified": 0,
        "idempotency_created": 0,
        "forbidden_public_fields": (),
    }
    values.update(changes)
    return VerificationInput(**values)


def test_all_exact_gates_pass_for_consistent_migration():
    report = evaluate_gates(valid_input())

    assert report.passed is True
    assert all(gate.passed for gate in report.gates)


def test_failed_media_and_identity_conflicts_block_gate():
    report = evaluate_gates(
        valid_input(media_failed=1, identity_conflicts=2)
    )

    assert report.passed is False
    failed = {gate.code for gate in report.gates if not gate.passed}
    assert failed == {"identity_conflicts", "media_failed"}


def test_listing_and_advertisement_counts_are_not_mixed():
    report = evaluate_gates(valid_input(target_advertisements=4))

    assert report.passed is False
    failed = {gate.code for gate in report.gates if not gate.passed}
    assert "advertisement_count" in failed
    assert "listing_count" not in failed


def test_idempotency_and_public_schema_leaks_block_gate():
    report = evaluate_gates(
        valid_input(
            idempotency_created=1,
            forbidden_public_fields=("business_account_id",),
        )
    )

    assert report.passed is False
    failed = {gate.code for gate in report.gates if not gate.passed}
    assert failed == {"idempotency", "public_schema_leak"}


class AsyncStore:
    def __init__(self, session):
        self.sync = session

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def get(self, model, key, **kwargs):
        return self.sync.get(model, key)


def empty_source() -> sqlite3.Connection:
    source = sqlite3.connect(":memory:")
    source.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY);
        CREATE TABLE businesses (id INTEGER PRIMARY KEY);
        CREATE TABLE item_groups (id INTEGER PRIMARY KEY, kind TEXT);
        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            kind TEXT,
            photo_file TEXT
        );
        CREATE TABLE listings (id INTEGER PRIMARY KEY);
        CREATE TABLE listing_media (
            id INTEGER PRIMARY KEY,
            tg_file_id TEXT
        );
        CREATE TABLE advertisements (
            id INTEGER PRIMARY KEY,
            image_file TEXT,
            mobile_image_file TEXT
        );
        """
    )
    return source


@pytest.mark.asyncio
async def test_verification_ignores_evidence_from_previous_run():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            MigrationRun.__table__,
            LegacyIdMap.__table__,
            MigrationIssue.__table__,
            MediaMigration.__table__,
            CatalogItem.__table__,
            Listing.__table__,
            Advertisement.__table__,
        ),
    )
    session = Session(engine, expire_on_commit=False)
    now = datetime(2026, 7, 29, tzinfo=UTC)
    previous = MigrationRun(
        id=1,
        source_database_sha256="a" * 64,
        media_manifest_sha256="b" * 64,
        schema_version="0003_phase3c_content",
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.VERIFY,
        status=MigrationStatus.COMPLETED,
        counters_json={},
        error_count=0,
        started_at=now,
    )
    current = MigrationRun(
        id=2,
        source_database_sha256="a" * 64,
        media_manifest_sha256="b" * 64,
        schema_version="0003_phase3c_dual_accounts_v2",
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.VERIFY,
        status=MigrationStatus.RUNNING,
        counters_json={},
        error_count=0,
        started_at=now,
    )
    session.add_all(
        [
            previous,
            current,
            LegacyIdMap(
                id=1,
                entity_type="listing",
                legacy_id=999,
                target_id=999,
                source_row_hash="c" * 64,
                mapping_status="mapped",
                review_reason="",
                last_run_id=previous.id,
            ),
            MigrationIssue(
                id=1,
                migration_run_id=previous.id,
                entity_type="user_account",
                legacy_id=999,
                issue_code="identity.identifiers_disagree",
                details_json={},
                resolved=False,
                created_at=now,
            ),
            MediaMigration(
                id=1,
                migration_run_id=previous.id,
                entity_type="catalog_item",
                legacy_id=999,
                slot="primary",
                source_reference_fingerprint="d" * 64,
                destination_object_key="",
                sha256="",
                content_type="",
                size_bytes=0,
                state=MediaMigrationState.FAILED,
                attempts=1,
                last_error_code="media.old_failure",
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    session.commit()
    source = empty_source()
    try:
        report = await verify_migration(
            AsyncStore(session),
            source,
            current,
        )
    finally:
        source.close()
        session.close()
        engine.dispose()

    assert report.passed is True
