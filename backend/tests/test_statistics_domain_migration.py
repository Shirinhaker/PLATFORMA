from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from app.cash_register.model import CashReceipt
from app.inventory.model import InventoryItem
from app.statistics.router import router as statistics_router


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/migrations/versions/0020_statistics_query_indexes.py"
MAIN = ROOT / "backend/app/main.py"


def load_migration():
    spec = spec_from_file_location("statistics_query_indexes", MIGRATION)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_statistics_migration_adds_waiter_attribution_and_query_index():
    migration = load_migration()

    assert migration.revision == "0020_statistics_query_indexes"
    assert migration.down_revision == "0019_education_domain"
    source = MIGRATION.read_text(encoding="utf-8")
    assert "ix_inventory_items_business_stock_qty" in source
    assert "track_stock IS true" in source
    assert "dining_bookings" in migration.WAITER_BACKFILL_SQL
    assert "dining_orders" in migration.WAITER_BACKFILL_SQL
    assert "receipt.business_account_id = source.account_id" in (
        migration.WAITER_BACKFILL_SQL
    )
    assert "create_table" not in source

    indexes = {index.name: index for index in InventoryItem.__table__.indexes}
    assert "ix_inventory_items_business_stock_qty" in indexes
    assert "waiter_staff_id" in CashReceipt.__table__.columns
    assert "waiter_name_snapshot" in CashReceipt.__table__.columns


def test_statistics_router_exposes_v1656_report_and_navigation():
    routes = {
        (route.path, method)
        for route in statistics_router.routes
        for method in (route.methods or set())
    }

    assert ("/api/v1/statistics", "GET") in routes
    assert ("/api/v1/statistics/nav", "GET") in routes


def test_statistics_service_and_router_are_wired_into_the_application():
    source = MAIN.read_text(encoding="utf-8")

    assert "app.state.statistics_service = StatisticsService(" in source
    assert "app.include_router(statistics_router)" in source
