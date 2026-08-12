from datetime import UTC, datetime
import sqlite3

import pytest

from app.legacy_migration.model import (
    MigrationEnvironment,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
)
from app.legacy_migration.profile_media_verify_v8 import (
    ProfileMediaExpectation,
    expected_profile_media,
    verify_profile_media_counter,
)
from app.legacy_migration.runner_v6 import MIGRATION_SCHEMA_VERSION


def _source() -> sqlite3.Connection:
    source = sqlite3.connect(":memory:")
    source.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY);
        CREATE TABLE businesses (id INTEGER PRIMARY KEY);
        CREATE TABLE profile_images (
            owner_kind TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            mime_type TEXT,
            content BLOB,
            updated_at INTEGER
        );
        INSERT INTO users (id) VALUES (1);
        INSERT INTO businesses (id) VALUES (5);
        INSERT INTO profile_images(owner_kind,owner_id,mime_type,content,updated_at)
        VALUES
          ('user',1,'image/jpeg',x'FFD8FF',1),
          ('business',5,'image/png',x'89504E47',1),
          ('user',99,'image/jpeg',x'FFD8FF',1),
          ('unknown',1,'image/jpeg',x'FFD8FF',1);
        """
    )
    return source


def _run(counter: dict[str, int]) -> MigrationRun:
    return MigrationRun(
        id=9,
        source_database_sha256="source",
        media_manifest_sha256="manifest",
        schema_version=MIGRATION_SCHEMA_VERSION,
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.VERIFY,
        status=MigrationStatus.COMPLETED,
        counters_json={
            "verify": {"passed": True},
            "profile_media": counter,
        },
        error_count=0,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )


def test_expected_profile_media_counts_only_real_supported_owners():
    source = _source()
    try:
        expectation = expected_profile_media(source)
    finally:
        source.close()

    assert expectation == ProfileMediaExpectation(
        total=2,
        users=1,
        businesses=1,
    )


def test_profile_media_gate_requires_exact_created_plus_reused_count():
    values = verify_profile_media_counter(
        _run(
            {
                "created": 1,
                "reused": 1,
                "updated": 0,
                "quarantined": 0,
                "issues": 0,
            }
        ),
        ProfileMediaExpectation(total=2, users=1, businesses=1),
    )

    assert values["migrated"] == 2

    with pytest.raises(RuntimeError, match="profile_media_count_mismatch"):
        verify_profile_media_counter(
            _run(
                {
                    "created": 1,
                    "reused": 0,
                    "updated": 0,
                    "quarantined": 0,
                    "issues": 0,
                }
            ),
            ProfileMediaExpectation(total=2, users=1, businesses=1),
        )


def test_profile_media_gate_rejects_missing_or_dirty_counter():
    run = _run({})
    run.counters_json = {"verify": {"passed": True}}
    with pytest.raises(RuntimeError, match="profile_media_counter_missing"):
        verify_profile_media_counter(
            run,
            ProfileMediaExpectation(total=0, users=0, businesses=0),
        )

    with pytest.raises(RuntimeError, match="profile_media_counter_not_clean"):
        verify_profile_media_counter(
            _run(
                {
                    "created": 2,
                    "reused": 0,
                    "updated": 0,
                    "quarantined": 1,
                    "issues": 0,
                }
            ),
            ProfileMediaExpectation(total=2, users=1, businesses=1),
        )


def test_profile_media_gate_requires_source_tables():
    source = sqlite3.connect(":memory:")
    source.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
    try:
        with pytest.raises(RuntimeError, match="profile_media_source_table_missing"):
            expected_profile_media(source)
    finally:
        source.close()
