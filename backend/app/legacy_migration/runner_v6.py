from app.legacy_migration import runner as base_runner
from app.legacy_migration.profile_parity_v7 import (
    reconcile_accounts,
    reconcile_businesses,
)


MIGRATION_SCHEMA_VERSION = "0006_phase3c_complete_cabinet_v1"


def build_database_runner(database, settings, storage):
    """Build the complete v1656 cabinet migration runner safely."""
    base_runner.MIGRATION_SCHEMA_VERSION = MIGRATION_SCHEMA_VERSION
    base_runner.reconcile_accounts = reconcile_accounts
    base_runner.reconcile_businesses = reconcile_businesses
    return base_runner.build_database_runner(database, settings, storage)


MigrationRunner = base_runner.MigrationRunner
ProductionApproval = base_runner.ProductionApproval
ProductionGateError = base_runner.ProductionGateError
SnapshotFingerprintError = base_runner.SnapshotFingerprintError
STAGES = base_runner.STAGES
