"""Compatibility exports for offline migration commands and old tests."""

from app.core.legacy_ids import LegacyIdMap
from app.core.states import (
    OWNER_STATE_ENUM,
    REVIEW_STATE_ENUM,
    OwnerState,
    ReviewState,
)
from app.db.migration_models import (
    MEDIA_MIGRATION_STATE_ENUM,
    MIGRATION_ENVIRONMENT_ENUM,
    MIGRATION_STAGE_ENUM,
    MIGRATION_STATUS_ENUM,
    MediaMigration,
    MediaMigrationState,
    MigrationEnvironment,
    MigrationIssue,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
    enum_type,
)

__all__ = [
    "LegacyIdMap",
    "OWNER_STATE_ENUM",
    "REVIEW_STATE_ENUM",
    "OwnerState",
    "ReviewState",
    "MEDIA_MIGRATION_STATE_ENUM",
    "MIGRATION_ENVIRONMENT_ENUM",
    "MIGRATION_STAGE_ENUM",
    "MIGRATION_STATUS_ENUM",
    "MediaMigration",
    "MediaMigrationState",
    "MigrationEnvironment",
    "MigrationIssue",
    "MigrationRun",
    "MigrationStage",
    "MigrationStatus",
    "enum_type",
]
