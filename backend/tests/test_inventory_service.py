from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.catalog.model import CatalogGroup, CatalogItem
from app.core.errors import ApiError
from app.db.base import Base
from app.expenses.model import Expense, ExpenseCategory
from app.inventory.model import (
    InventoryItem,
    ProductionBatch,
    RecipeIngredient,
    StockBatch,
    StockMove,
)
from app.inventory.schemas import IngredientWrite, InventoryItemWrite, StockMoveCreate
from app.inventory.repository import InventoryRepository
from app.inventory.service import InventoryService
from app.legacy_migration.model import OwnerState, ReviewState
from app.profiles.model import BusinessProfile


NOW = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)


class AsyncStore:
    def __init__(self, sync: Session) -> None:
        self.sync = sync
        self.sequences: dict[str, int] = {}

    def add(self, value):
        self.sync.add(value)

    def add_all(self, values):
        self.sync.add_all(values)

    async def delete(self, value):
        self.sync.delete(value)

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def get(self, model, identity, **_kwargs):
        return self.sync.get(model, identity)

    async def flush(self):
        for value in list(self.sync.new):
            if not hasattr(value, "id") or value.id is not None:
                continue
            table = value.__table__.name
            if table not in self.sequences:
                highest = self.sync.scalar(select(func.max(value.__table__.c.id)))
                self.sequences[table] = int(highest or 0)
            self.sequences[table] += 1
            value.id = self.sequences[table]
        self.sync.flush()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


def account(identifier: int) -> Account:
    return Account(
        id=identifier,
        account_type=AccountType.BUSINESS,
        login=f"business_{identifier}",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def catalog_item(identifier: int, business_id: int, name: str, unit: str) -> CatalogItem:
    return CatalogItem(
        id=identifier,
        business_account_id=business_id,
        source_record_key=str(identifier),
        catalog_group_id=None,
        owner_name_snapshot="Test biznes",
        name=name,
        price_text="",
        unit=unit,
        note="",
        kind="product",
        queue_enabled=False,
        image_object_key="",
        status="active",
        owner_state=OwnerState.LINKED,
        review_state=ReviewState.READY,
        migration_run_id=None,
        created_at=NOW,
        updated_at=NOW,
    )


def business_profile(identifier: int, direction: str) -> BusinessProfile:
    return BusinessProfile(
        account_id=identifier,
        name="Test biznes",
        phone="",
        description="",
        public_username=f"inventory_test_{identifier}",
        direction=direction,
        activity_type="",
        address="",
        work_hours={},
        pay_card="",
        pay_holder="",
        pay_qr_object_key="",
        director="",
        tax_id="",
        logo_object_key="",
        logo_x=50,
        logo_y=50,
        logo_zoom=1,
        followers_count=0,
        following_count=0,
        rating_sum=0,
        rating_count=0,
        map_visible=False,
        dashboard_snapshot={},
        recent_activity=[],
        cabinet_payload={},
    )


@pytest.fixture
def inventory_context():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            BusinessProfile.__table__,
            CatalogGroup.__table__,
            CatalogItem.__table__,
            InventoryItem.__table__,
            StockMove.__table__,
            StockBatch.__table__,
            Base.metadata.tables["inventory_batch_consumptions"],
            RecipeIngredient.__table__,
            ProductionBatch.__table__,
            Base.metadata.tables["inventory_production_inputs"],
            ExpenseCategory.__table__,
            Expense.__table__,
        ),
    )
    with Session(engine, expire_on_commit=False) as seed:
        seed.add_all((
            account(1),
            account(2),
            business_profile(1, "Umumiy ovqatlanish"),
            business_profile(2, "Savdo"),
            catalog_item(11, 1, "Un", "kg"),
            catalog_item(12, 1, "Non", "dona"),
            catalog_item(13, 1, "Suv", "l"),
            catalog_item(21, 2, "Begona mahsulot", "dona"),
            InventoryItem(
                id=101,
                business_account_id=1,
                catalog_item_id=11,
                legacy_source_id=11,
                track_stock=True,
                stock_type="raw_material",
                stock_qty=Decimal("0"),
                cost_price=0,
                min_qty=Decimal("1"),
                fifo_initialized=True,
                created_at=NOW,
                updated_at=NOW,
            ),
            InventoryItem(
                id=102,
                business_account_id=1,
                catalog_item_id=12,
                legacy_source_id=12,
                track_stock=True,
                stock_type="ready_food",
                stock_qty=Decimal("0"),
                cost_price=0,
                min_qty=Decimal("0"),
                fifo_initialized=True,
                created_at=NOW,
                updated_at=NOW,
            ),
            InventoryItem(
                id=201,
                business_account_id=2,
                catalog_item_id=21,
                legacy_source_id=21,
                track_stock=True,
                stock_type="ready_food",
                stock_qty=Decimal("0"),
                cost_price=0,
                min_qty=Decimal("0"),
                fifo_initialized=True,
                created_at=NOW,
                updated_at=NOW,
            ),
        ))
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    service = InventoryService(sessions, now_provider=lambda: NOW)
    try:
        yield service, engine
    finally:
        engine.dispose()


async def test_fifo_production_and_recipe_are_one_atomic_transaction(inventory_context):
    service, engine = inventory_context
    raw_receipt = await service.create_move(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        body=StockMoveCreate(item_id=101, delta=10, cost=100, note="1-partiya"),
    )
    await service.create_move(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        body=StockMoveCreate(
            item_id=102,
            delta=2,
            ingredients=[IngredientWrite(item_id=101, qty=4)],
            save_recipe=True,
            note="Non yopildi",
        ),
    )

    with Session(engine) as session:
        raw = session.get(InventoryItem, 101)
        ready = session.get(InventoryItem, 102)
        assert raw is not None and raw.stock_qty == Decimal("6.000")
        assert ready is not None and ready.stock_qty == Decimal("2.000")
        assert ready.cost_price == 200
        raw_batch = session.scalar(
            select(StockBatch).where(StockBatch.inventory_item_id == 101)
        )
        ready_batch = session.scalar(
            select(StockBatch).where(StockBatch.inventory_item_id == 102)
        )
        assert raw_batch is not None and raw_batch.qty_remaining == Decimal("6.000")
        assert ready_batch is not None and ready_batch.unit_cost == 200
        production = session.scalar(select(ProductionBatch))
        assert production is not None and production.total_cost == 400
        recipe = session.scalar(select(RecipeIngredient))
        assert recipe is not None and recipe.qty_per_unit == Decimal("2.000000")

    with pytest.raises(ApiError) as used_receipt:
        await service.delete_move(
            business_account_id=1,
            actor_staff_id=None,
            permissions=None,
            move_id=raw_receipt.move_id,
        )
    assert used_receipt.value.status_code == 409


async def test_failed_fifo_move_rolls_back_quantity_and_owner_scope(inventory_context):
    service, engine = inventory_context
    with pytest.raises(ApiError) as missing:
        await service.create_move(
            business_account_id=1,
            actor_staff_id=None,
            permissions=None,
            body=StockMoveCreate(item_id=101, delta=-1),
        )
    assert missing.value.code == "inventory_fifo_insufficient"

    with Session(engine) as session:
        item = session.get(InventoryItem, 101)
        assert item is not None and item.stock_qty == Decimal("0.000")
        assert session.scalar(select(func.count(StockMove.id))) == 0

    with pytest.raises(ApiError) as foreign:
        await service.create_move(
            business_account_id=1,
            actor_staff_id=None,
            permissions=None,
            body=StockMoveCreate(item_id=201, delta=1),
        )
    assert foreign.value.code == "inventory_item_not_found"


async def test_manual_outflow_delete_restores_exact_fifo_batch(inventory_context):
    service, engine = inventory_context
    await service.create_move(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        body=StockMoveCreate(item_id=101, delta=5, cost=90),
    )
    outgoing = await service.create_move(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        body=StockMoveCreate(item_id=101, delta=-2, note="Sinov chiqimi"),
    )
    await service.delete_move(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        move_id=outgoing.move_id,
    )

    with Session(engine) as session:
        item = session.get(InventoryItem, 101)
        batch = session.scalar(select(StockBatch))
        assert item is not None and item.stock_qty == Decimal("5.000")
        assert batch is not None and batch.qty_remaining == Decimal("5.000")
        assert session.get(StockMove, outgoing.move_id) is None


async def test_production_only_staff_cannot_edit_raw_stock(inventory_context):
    service, _engine = inventory_context
    with pytest.raises(ApiError) as forbidden:
        await service.create_move(
            business_account_id=1,
            actor_staff_id=77,
            permissions=("production",),
            body=StockMoveCreate(item_id=101, delta=1, cost=100),
        )
    assert forbidden.value.code == "inventory_production_only"

    with pytest.raises(ApiError) as no_permission:
        await service.list_items(
            business_account_id=1,
            permissions=("kassa",),
        )
    assert no_permission.value.code == "staff_permission_required"


async def test_fifo_uses_oldest_batches_and_calculates_weighted_cost(inventory_context):
    service, engine = inventory_context
    await service.create_move(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        body=StockMoveCreate(item_id=101, delta=2, cost=100),
    )
    await service.create_move(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        body=StockMoveCreate(item_id=101, delta=3, cost=200),
    )
    outgoing = await service.create_move(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        body=StockMoveCreate(item_id=101, delta=-4),
    )

    assert outgoing.unit_cost == 150
    with Session(engine) as session:
        batches = list(session.scalars(
            select(StockBatch).order_by(StockBatch.created_at, StockBatch.id)
        ).all())
        assert [row.qty_remaining for row in batches] == [
            Decimal("0.000"),
            Decimal("1.000"),
        ]


async def test_failed_production_restores_every_quantity(inventory_context):
    service, engine = inventory_context
    await service.create_move(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        body=StockMoveCreate(item_id=101, delta=2, cost=0),
    )
    with pytest.raises(ApiError) as missing_cost:
        await service.create_move(
            business_account_id=1,
            actor_staff_id=None,
            permissions=None,
            body=StockMoveCreate(
                item_id=102,
                delta=1,
                ingredients=[IngredientWrite(item_id=101, qty=1)],
            ),
        )
    assert missing_cost.value.code == "inventory_fifo_cost_required"

    with Session(engine) as session:
        raw = session.get(InventoryItem, 101)
        ready = session.get(InventoryItem, 102)
        assert raw is not None and raw.stock_qty == Decimal("2.000")
        assert ready is not None and ready.stock_qty == Decimal("0.000")
        assert session.scalar(select(func.count(ProductionBatch.id))) == 0


async def test_repository_uses_postgresql_row_locks_for_parallel_stock_changes():
    captured = []

    class EmptyResult:
        def first(self):
            return None

        def all(self):
            return []

    class CaptureSession:
        async def execute(self, statement):
            captured.append(statement)
            return EmptyResult()

        async def scalars(self, statement):
            captured.append(statement)
            return EmptyResult()

    repository = InventoryRepository()
    session = CaptureSession()
    await repository.owned_item(
        session,
        business_account_id=1,
        inventory_item_id=101,
        lock=True,
    )
    await repository.fifo_batches(
        session,
        business_account_id=1,
        inventory_item_id=101,
        lock=True,
    )

    sql = [
        str(statement.compile(dialect=postgresql.dialect())).upper()
        for statement in captured
    ]
    assert "FOR UPDATE OF INVENTORY_ITEMS" in sql[0]
    assert "FOR UPDATE" in sql[1]


async def test_item_configuration_starts_at_zero_without_fabricating_history(
    inventory_context,
):
    service, engine = inventory_context
    configured = await service.configure_item(
        business_account_id=1,
        permissions=None,
        catalog_item_id=13,
        body=InventoryItemWrite(
            track_stock=True,
            stock_type="raw_material",
            min_qty=2.5,
        ),
    )

    assert configured.name == "Suv"
    assert configured.stock_qty == 0
    assert configured.min_qty == 2.5
    with Session(engine) as session:
        assert session.scalar(select(func.count(StockMove.id))) == 0


async def test_production_staff_sees_quantity_but_not_costs(inventory_context):
    service, _engine = inventory_context
    await service.create_move(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        body=StockMoveCreate(item_id=101, delta=3, cost=125),
    )
    result = await service.list_items(
        business_account_id=1,
        permissions=("production",),
    )
    raw = next(item for item in result.items if item.id == 101)

    assert raw.stock_qty == 3
    assert raw.cost_price == 0
    assert raw.fifo_next_cost == 0
    assert raw.fifo_value == 0
    assert raw.price == ""


async def test_stock_receipt_creates_and_deletes_one_atomic_expense(
    inventory_context,
):
    service, engine = inventory_context
    receipt = await service.create_move(
        business_account_id=1,
        actor_staff_id=None,
        actor_name="Muhr",
        permissions=None,
        body=StockMoveCreate(
            item_id=101,
            delta=2.5,
            cost=100_000,
            note="Yetkazib beruvchi",
        ),
    )

    with Session(engine) as session:
        expense = session.scalar(select(Expense))
        assert expense is not None
        assert expense.business_account_id == 1
        assert expense.inventory_stock_move_id == receipt.move_id
        assert expense.category == "Tovar xaridi"
        assert expense.amount == 250_000
        assert expense.note == "Un — Yetkazib beruvchi"
        assert expense.source == "stock"
        assert expense.actor_name_snapshot == "Muhr"

    await service.delete_move(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        move_id=receipt.move_id,
    )
    with Session(engine) as session:
        assert session.scalar(select(func.count(Expense.id))) == 0
        item = session.get(InventoryItem, 101)
        assert item is not None and item.stock_qty == Decimal("0.000")


async def test_production_output_does_not_duplicate_input_purchase_expense(
    inventory_context,
):
    service, engine = inventory_context
    await service.create_move(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        body=StockMoveCreate(item_id=101, delta=4, cost=100_000),
    )
    await service.create_move(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        body=StockMoveCreate(
            item_id=102,
            delta=2,
            ingredients=[IngredientWrite(item_id=101, qty=4)],
        ),
    )

    with Session(engine) as session:
        expenses = list(session.scalars(select(Expense)).all())
        assert [(row.category, row.amount) for row in expenses] == [
            ("Tovar xaridi", 400_000)
        ]
