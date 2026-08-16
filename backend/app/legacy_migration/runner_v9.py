from app.legacy_migration import runner as base_runner
from app.legacy_migration.cabinet_parity_v8 import (
    reconcile_accounts,
    reconcile_businesses,
)
from app.legacy_migration.real_source_v9 import open_real_snapshot

MIGRATION_SCHEMA_VERSION = "0009_phase3c_real_subscriptions_v1"


def build_database_runner(database, settings, storage):
    """Build the V9 runner with real-business subscription parity."""
    base_runner.MIGRATION_SCHEMA_VERSION = MIGRATION_SCHEMA_VERSION
    base_runner.reconcile_accounts = reconcile_accounts
    base_runner.reconcile_businesses = reconcile_businesses
    base_runner.open_immutable = open_real_snapshot
    return base_runner.build_database_runner(database, settings, storage)


MigrationRunner = base_runner.MigrationRunner
ProductionApproval = base_runner.ProductionApproval
ProductionGateError = base_runner.ProductionGateError
SnapshotFingerprintError = base_runner.SnapshotFingerprintError
STAGES = base_runner.STAGES
