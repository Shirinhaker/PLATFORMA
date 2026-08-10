from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0037_inventory_live_completion.py"
)


def _migration():
    spec = spec_from_file_location("inventory_live_completion", MIGRATION)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inventory_completion_extends_current_head_without_overwriting_stock():
    migration = _migration()
    source = MIGRATION.read_text(encoding="utf-8")

    assert migration.revision == "0037_inventory_live_completion"
    assert migration.down_revision == "0036_subscription_payments"
    assert "cabinet_resources" in migration.BACKFILL_MISSING_ITEMS_SQL
    assert "cabinet_payload" in migration.BACKFILL_MISSING_ITEMS_SQL
    assert "NOT EXISTS" in migration.BACKFILL_MISSING_ITEMS_SQL
    assert "ON CONFLICT (catalog_item_id) DO NOTHING" in source
    assert "DO UPDATE SET" not in migration.BACKFILL_MISSING_ITEMS_SQL
    assert "inventory_stock_batches" in migration.BACKFILL_MISSING_FIFO_SQL


def test_inventory_completion_downgrade_never_deletes_business_history():
    source = MIGRATION.read_text(encoding="utf-8").casefold()
    downgrade = source[source.index("def downgrade()") :]

    assert "delete from" not in downgrade
    assert "drop_table" not in downgrade
