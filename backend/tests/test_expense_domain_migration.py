from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from app.expenses.model import Expense, ExpenseCategory
from app.expenses.router import router as expenses_router


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/migrations/versions/0018_expense_domain.py"
ALEMBIC_ENV = ROOT / "backend/migrations/env.py"


def load_migration():
    spec = spec_from_file_location("expense_domain_migration", MIGRATION)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_expense_models_keep_owner_legacy_and_stock_link_constraints():
    expense_indexes = {index.name: index for index in Expense.__table__.indexes}
    category_indexes = {
        index.name: index for index in ExpenseCategory.__table__.indexes
    }

    assert Expense.__tablename__ == "expenses"
    assert ExpenseCategory.__tablename__ == "expense_categories"
    assert expense_indexes["uq_expenses_business_legacy"].unique is True
    assert expense_indexes["uq_expenses_stock_move"].unique is True
    assert "ix_expenses_business_created" in expense_indexes
    assert category_indexes["uq_expense_categories_business_legacy"].unique is True
    assert category_indexes["uq_expense_categories_business_name"].unique is True
    assert Expense.__table__.c.business_account_id.foreign_keys
    assert Expense.__table__.c.inventory_stock_move_id.foreign_keys


def test_migration_backfills_expenses_and_categories_idempotently():
    migration = load_migration()

    assert migration.revision == "0018_expense_domain"
    assert migration.down_revision == "0017_debt_ledger_domain"
    assert "'expenses'" in migration.EXPENSE_BACKFILL_SQL
    assert "'expense_cats'" in migration.CATEGORY_BACKFILL_SQL
    assert "cabinet_resources" in migration.EXPENSE_BACKFILL_SQL
    assert "business_profiles" in migration.EXPENSE_BACKFILL_SQL
    assert "ON CONFLICT (business_account_id, legacy_source_id)" in (
        migration.EXPENSE_BACKFILL_SQL
    )
    assert "ON CONFLICT (business_account_id, legacy_source_id)" in (
        migration.CATEGORY_BACKFILL_SQL
    )


def test_migration_relinks_stock_expenses_to_normalized_inventory_moves():
    migration = load_migration()

    assert "inventory_stock_moves" in migration.EXPENSE_BACKFILL_SQL
    assert "legacy_source_id" in migration.EXPENSE_BACKFILL_SQL
    assert "stock_move_id" in migration.EXPENSE_BACKFILL_SQL
    assert "inventory_stock_move_id" in migration.EXPENSE_BACKFILL_SQL
    assert "ondelete=\"CASCADE\"" in MIGRATION.read_text(encoding="utf-8")


def test_alembic_metadata_and_router_register_expense_domain():
    source = ALEMBIC_ENV.read_text(encoding="utf-8")
    assert "from app.expenses import model as expenses_model" in source

    routes = {
        (route.path, method)
        for route in expenses_router.routes
        for method in (route.methods or set())
    }
    assert ("/api/v1/expenses", "GET") in routes
    assert ("/api/v1/expenses", "POST") in routes
    assert ("/api/v1/expenses/categories", "GET") in routes
    assert ("/api/v1/expenses/categories", "POST") in routes
    assert ("/api/v1/expenses/{expense_id}", "DELETE") in routes
