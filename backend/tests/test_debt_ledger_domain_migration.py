from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from app.cash_register.model import CashReceipt
from app.debt_ledger.model import Debtor, DebtTransaction
from app.orders.model import Order


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/migrations/versions/0017_debt_ledger_domain.py"


def load_migration():
    spec = spec_from_file_location("debt_ledger_migration", MIGRATION)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_debt_models_scope_legacy_and_order_debt_constraints():
    debtor_indexes = {index.name for index in Debtor.__table__.indexes}
    transaction_indexes = {
        index.name for index in DebtTransaction.__table__.indexes
    }

    assert "uq_debtors_business_legacy" in debtor_indexes
    assert "uq_debt_transactions_business_legacy" in transaction_indexes
    assert "uq_debt_transactions_order_debt" in transaction_indexes
    assert DebtTransaction.__table__.c.debtor_id.foreign_keys
    assert "debtor_id" in CashReceipt.__table__.c
    assert "ix_cash_receipts_debtor" in {
        index.name for index in CashReceipt.__table__.indexes
    }
    assert "debtor_id" in Order.__table__.c


def test_migration_backfills_both_legacy_names_without_duplicate_transactions():
    migration = load_migration()

    assert migration.revision == "0017_debt_ledger_domain"
    assert migration.down_revision == "0016_cash_register_domain"
    transaction_sql = migration.TRANSACTION_BACKFILL_SQL
    assert "'qarz_transactions'" in transaction_sql
    assert "'qarz_tx'" in transaction_sql
    assert "transaction_sources AS" in transaction_sql
    assert "CASE resource WHEN 'qarz_transactions' THEN 0 ELSE 1 END" in transaction_sql
    assert "DISTINCT ON" in transaction_sql
    assert "pg_input_is_valid" in transaction_sql
    assert "ON CONFLICT (business_account_id, legacy_source_id)" in transaction_sql


def test_migration_links_legacy_debt_to_cash_receipts_and_orders():
    migration = load_migration()

    assert "qarz_tx_id" in migration.CASH_LINK_BACKFILL_SQL
    assert "line.legacy_source_key = 'sales:' || source.source_key" in (
        migration.CASH_LINK_BACKFILL_SQL
    )
    assert "SET cash_receipt_id = resolved.receipt_id" in (
        migration.CASH_LINK_BACKFILL_SQL
    )
    assert "debtor.legacy_source_id = receipt.legacy_debtor_source_id" in (
        migration.RECEIPT_DEBTOR_BACKFILL_SQL
    )
    assert "receipt.pay_type = 'qarz'" in migration.ORDER_DEBTOR_BACKFILL_SQL
