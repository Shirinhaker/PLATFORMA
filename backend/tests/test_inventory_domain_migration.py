import importlib.util
from pathlib import Path

from app.inventory.model import (
    InventoryItem,
    ProductionBatch,
    ProductionInput,
    RecipeIngredient,
    StockBatch,
    StockBatchConsumption,
    StockMove,
)
from app.inventory.router import router as inventory_router


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0015_inventory_domain.py"
)
ALEMBIC_ENV = MIGRATION.parents[1] / "env.py"


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("inventory_domain_migration", MIGRATION)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inventory_models_keep_owner_boundaries_and_fifo_indexes():
    assert InventoryItem.__tablename__ == "inventory_items"
    assert StockMove.__tablename__ == "inventory_stock_moves"
    assert StockBatch.__tablename__ == "inventory_stock_batches"
    assert StockBatchConsumption.__tablename__ == "inventory_batch_consumptions"
    assert RecipeIngredient.__tablename__ == "inventory_recipe_ingredients"
    assert ProductionBatch.__tablename__ == "inventory_production_batches"
    assert ProductionInput.__tablename__ == "inventory_production_inputs"

    item_indexes = {index.name: index for index in InventoryItem.__table__.indexes}
    move_indexes = {index.name: index for index in StockMove.__table__.indexes}
    batch_indexes = {index.name: index for index in StockBatch.__table__.indexes}

    assert item_indexes["uq_inventory_items_catalog"].unique is True
    assert item_indexes["uq_inventory_items_business_legacy"].unique is True
    assert "ix_inventory_items_business_tracked" in item_indexes
    assert move_indexes["uq_inventory_stock_moves_business_legacy"].unique is True
    assert "ix_inventory_stock_moves_item_created" in move_indexes
    assert "ix_inventory_stock_batches_fifo" in batch_indexes

    assert InventoryItem.__table__.c.business_account_id.foreign_keys
    assert InventoryItem.__table__.c.catalog_item_id.foreign_keys
    assert StockMove.__table__.c.inventory_item_id.foreign_keys
    assert StockBatchConsumption.__table__.c.batch_id.foreign_keys
    assert ProductionInput.__table__.c.production_batch_id.foreign_keys


def test_inventory_migration_backfills_v1656_rows_idempotently():
    source = MIGRATION.read_text(encoding="utf-8")
    upper = source.upper()

    assert 'revision = "0015_inventory_domain"' in source
    assert 'down_revision = "0014_staff_domain"' in source
    for table in (
        "inventory_items",
        "inventory_stock_moves",
        "inventory_stock_batches",
        "inventory_batch_consumptions",
        "inventory_recipe_ingredients",
        "inventory_production_batches",
        "inventory_production_inputs",
    ):
        assert f'"{table}"' in source

    assert "cabinet_resources" in source
    assert "cabinet_records" in source
    assert "cabinet_record_fields" in source
    assert "business_profiles" in source
    assert "cabinet_payload" in source
    assert "catalog_items" in source
    assert "stock_moves" in source
    assert "stock_batches" in source
    assert "item_recipes" in source
    assert "production_batches" in source
    assert "ON CONFLICT" in upper
    assert "DO UPDATE" in upper


def test_inventory_backfill_statements_are_complete_postgresql_ctes():
    migration = _load_migration_module()

    for statement in (
        migration.INVENTORY_ITEM_BACKFILL_SQL,
        migration.STOCK_MOVE_BACKFILL_SQL,
        migration.STOCK_BATCH_BACKFILL_SQL,
        migration.RECIPE_BACKFILL_SQL,
        migration.PRODUCTION_BATCH_BACKFILL_SQL,
        migration.PRODUCTION_INPUT_BACKFILL_SQL,
        migration.CONSUMPTION_BACKFILL_SQL,
    ):
        assert statement.lstrip().startswith("WITH\n")
        assert "{{" not in statement


def test_inventory_migration_is_reversible_without_touching_kassa_or_orders():
    source = MIGRATION.read_text(encoding="utf-8")
    lowered = source.casefold()
    downgrade = source[source.index("def downgrade() -> None:") :]

    for forbidden in (
        "insert into sales",
        "insert into expenses",
        "update orders",
        "delete from orders",
    ):
        assert forbidden not in lowered
    assert downgrade.index('drop_table("inventory_production_inputs")') < downgrade.index(
        'drop_table("inventory_items")'
    )
    assert downgrade.index('drop_table("inventory_batch_consumptions")') < downgrade.index(
        'drop_table("inventory_stock_batches")'
    )


def test_alembic_metadata_registers_inventory_models():
    source = ALEMBIC_ENV.read_text(encoding="utf-8")
    assert "from app.inventory import model as inventory_model" in source


def test_inventory_router_exposes_only_typed_warehouse_endpoints():
    routes = {
        (route.path, method)
        for route in inventory_router.routes
        for method in (route.methods or set())
    }
    assert ("/api/v1/warehouse/items", "GET") in routes
    assert ("/api/v1/warehouse/items/{catalog_item_id}", "PUT") in routes
    assert ("/api/v1/warehouse/moves", "POST") in routes
    assert ("/api/v1/warehouse/moves/{move_id}", "DELETE") in routes
    assert ("/api/v1/warehouse/items/{inventory_item_id}/moves", "GET") in routes
    assert ("/api/v1/warehouse/items/{inventory_item_id}/recipe", "GET") in routes
    assert ("/api/v1/warehouse/production", "GET") in routes
    assert all("cabinet_payload" not in path for path, _method in routes)
