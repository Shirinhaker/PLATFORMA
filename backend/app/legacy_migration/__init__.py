"""Idempotent migration from the Koprik v1656 monolith."""

# V6 keeps the public runner API stable while replacing only the account and
# business reconciliation handlers. This avoids reusing the failed V5 schema
# run and leaves all other Phase 3C stages unchanged.
from app.legacy_migration import runner as _runner
from app.legacy_migration.reconcile_v6 import (
    reconcile_accounts,
    reconcile_businesses,
)

_runner.MIGRATION_SCHEMA_VERSION = "0004_phase3c_shared_login_v1"
_runner.reconcile_accounts = reconcile_accounts
_runner.reconcile_businesses = reconcile_businesses
