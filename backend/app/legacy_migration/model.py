from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OwnerState(str, Enum):
    LINKED = "linked"
    UNLINKED = "unlinked"


class ReviewState(str, Enum):
    READY = "ready"
    REVIEW_REQUIRED = "review_required"


class MigrationEnvironment(str, Enum):
    STAGING = "staging"
    PRODUCTION = "production"


class MigrationStage(str, Enum):
    SNAPSHOT = "snapshot"
    INVENTORY = "inventory"
    ACCOUNTS = "accounts"
    BUSINESSES = "businesses"
    CATALOG = "catalog"
    LISTINGS = "listings"
    ADVERTISEMENTS = "advertisements"
    MEDIA = "media"
    VERIFY = "verify"


class MigrationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MediaMigrationState(str, Enum):
    PENDING = "pending"
    COPIED = "copied"
    MISSING = "missing"
    INVALID = "invalid"
    FAILED = "failed"


def enum_type(enum: type[Enum], name: str) -> SqlEnum:
    return SqlEnum(
        enum,
        name=name,
        values_callable=lambda enum_class: [item.value for item in enum_class],
        validate_strings=True,
    )


OWNER_STATE_ENUM = enum_type(OwnerState, "owner_state")
REVIEW_STATE_ENUM = enum_type(ReviewState, "review_state")
MIGRATION_ENVIRONMENT_ENUM = enum_type(
    MigrationEnvironment,
    "migration_environment",
)
MIGRATION_STAGE_ENUM = enum_type(MigrationStage, "migration_stage")
MIGRATION_STATUS_ENUM = enum_type(MigrationStatus, "migration_status")
MEDIA_MIGRATION_STATE_ENUM = enum_type(
    MediaMigrationState,
    "media_migration_state",
)


class MigrationRun(Base):
    __tablename__ = "migration_runs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_database_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    media_manifest_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
    )
    schema_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="0003_phase3c_content",
    )
    environment: Mapped[MigrationEnvironment] = mapped_column(
        MIGRATION_ENVIRONMENT_ENUM,
        nullable=False,
    )
    stage: Mapped[MigrationStage] = mapped_column(
        MIGRATION_STAGE_ENUM,
        nullable=False,
    )
    status: Mapped[MigrationStatus] = mapped_column(
        MIGRATION_STATUS_ENUM,
        nullable=False,
    )
    counters_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approved_staging_run_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("migration_runs.id", ondelete="RESTRICT"),
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LegacyIdMap(Base):
    __tablename__ = "legacy_id_map"
    __table_args__ = (
        UniqueConstraint("entity_type", "legacy_id", name="uq_legacy_id_map"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    legacy_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_id: Mapped[int | None] = mapped_column(BigInteger)
    source_row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    mapping_status: Mapped[str] = mapped_column(String(40), nullable=False)
    review_reason: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        default="",
    )
    last_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("migration_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )


class MigrationIssue(Base):
    __tablename__ = "migration_issues"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    migration_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("migration_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    legacy_id: Mapped[int | None] = mapped_column(BigInteger)
    issue_code: Mapped[str] = mapped_column(String(160), nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    resolved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MediaMigration(Base):
    __tablename__ = "media_migration"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "legacy_id",
            "slot",
            name="uq_media_migration_source_slot",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    migration_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("migration_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    legacy_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    slot: Mapped[str] = mapped_column(String(40), nullable=False)
    source_reference_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    destination_object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        default="",
    )
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    content_type: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="",
    )
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    state: Mapped[MediaMigrationState] = mapped_column(
        MEDIA_MIGRATION_STATE_ENUM,
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        default="",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
