from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from app.cash_register.model import CashReceipt, CashReceiptCounter, CashReceiptLine
from app.inventory.model import StockMove


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/migrations/versions/0016_cash_register_domain.py"


def load_migration():
    spec = spec_from_file_location("cash_register_migration", MIGRATION)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_cash_models_have_receipt_line_and_parallel_safety_constraints():
    assert CashReceiptCounter.__table__.c.business_account_id.primary_key
    assert "uq_cash_receipts_order" in {
        constraint.name for constraint in CashReceipt.__table__.constraints
    }
    assert CashReceiptLine.__table__.c.receipt_id.foreign_keys
    receipt_indexes = {index.name for index in CashReceipt.__table__.indexes}
    line_indexes = {index.name for index in CashReceiptLine.__table__.indexes}
    assert "uq_cash_receipts_legacy_group" in receipt_indexes
    assert "uq_cash_receipt_lines_legacy_source" in line_indexes
    assert "cash_sale_line_id" in StockMove.__table__.c


def test_migration_backfills_sales_with_fallback_and_idempotent_keys():
    migration = load_migration()

    assert migration.revision == "0016_cash_register_domain"
    assert migration.down_revision == "0015_inventory_domain"
    receipt_sql = migration.RECEIPT_BACKFILL_SQL
    line_sql = migration.LINE_BACKFILL_SQL
    assert "'sales', 'cash_transactions', 'cash_register_transactions'" in receipt_sql
    assert "row.resource = 'sales'" in receipt_sql
    assert "NOT EXISTS" in receipt_sql
    assert "ON CONFLICT (business_account_id, legacy_group_key)" in receipt_sql
    assert "ON CONFLICT (business_account_id, legacy_source_key)" in line_sql
    assert "inventory.legacy_source_id" in line_sql
    assert "CASE WHEN inventory.track_stock THEN inventory.id ELSE NULL END" in line_sql
    assert "target_order.legacy_source_id" in receipt_sql


def test_migration_relinks_fifo_and_initializes_receipt_counter():
    migration = load_migration()

    assert "source_type = 'cash_line'" in migration.CONSUMPTION_RELINK_SQL
    assert "line.legacy_source_key = 'sales:'" in migration.CONSUMPTION_RELINK_SQL
    assert "SET cash_sale_line_id = line.id" in migration.MOVE_RELINK_SQL
    assert "greatest(" in migration.COUNTER_BACKFILL_SQL
    assert "ON CONFLICT (business_account_id) DO UPDATE" in migration.COUNTER_BACKFILL_SQL
