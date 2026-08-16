from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.catalog.live_sync import sync_business_catalog
from app.catalog.model import CatalogGroup, CatalogItem
from app.db.base import Base
from app.inventory.live_sync import sync_business_inventory
from app.inventory.model import InventoryItem, StockBatch, StockMove
from app.staff.model import StaffMember  # noqa: F401 — StockMove FK metadata uchun.

NOW = datetime(2026, 8, 10, tzinfo=UTC)


class AsyncStore:
    def __init__(self, session: Session):
        self.sync = session
        self.sequences: dict[str, int] = {}

    def add(self, value):
        self.sync.add(value)

    async def delete(self, value):
        self.sync.delete(value)

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

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            CatalogGroup.__table__,
            CatalogItem.__table__,
            InventoryItem.__table__,
            StockMove.__table__,
            StockBatch.__table__,
        ),
    )
    session = Session(engine, expire_on_commit=False)
    session.add(
        Account(
            id=7,
            account_type=AccountType.BUSINESS,
            login="ombor_test",
            password_hash="hash",
            telegram_user_id=None,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.commit()
    try:
        yield AsyncStore(session)
    finally:
        session.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_new_tracked_product_gets_initial_fifo_stock_once(store):
    payload = {
        "item_groups": [],
        "items": [
            {
                "id": 11,
                "name": "Un",
                "kind": "product",
                "unit": "kg",
                "track_stock": 1,
                "stock_type": "raw_material",
                "stock_qty": 25.5,
                "min_qty": 4,
            }
        ],
    }
    await sync_business_catalog(
        store,
        account_id=7,
        owner_name="Oshxona",
        payload=payload,
        changed_resources={"items"},
    )
    await sync_business_inventory(
        store,
        account_id=7,
        payload=payload,
        changed_resources={"items"},
    )

    item = (await store.scalars(select(InventoryItem))).one()
    move = (await store.scalars(select(StockMove))).one()
    batch = (await store.scalars(select(StockBatch))).one()
    assert item.stock_type == "raw_material"
    assert float(item.stock_qty) == 25.5
    assert float(item.min_qty) == 4
    assert move.reason == "tuzatish"
    assert move.note == "Boshlang‘ich qoldiq"
    assert batch.source_move_id == move.id
    assert float(batch.qty_remaining) == 25.5

    payload["items"][0].update({"stock_qty": 99, "min_qty": 6})
    await sync_business_inventory(
        store,
        account_id=7,
        payload=payload,
        changed_resources={"items"},
    )
    assert float(item.stock_qty) == 25.5
    assert float(item.min_qty) == 6
    assert await store.scalar(select(func.count()).select_from(StockMove)) == 1

    payload["items"][0]["track_stock"] = 0
    await sync_business_inventory(
        store,
        account_id=7,
        payload=payload,
        changed_resources={"items"},
    )
    assert item.track_stock is False
    assert float(item.stock_qty) == 25.5


@pytest.mark.asyncio
async def test_service_and_untracked_product_do_not_create_warehouse_rows(store):
    payload = {
        "item_groups": [],
        "items": [
            {"id": 1, "name": "Yetkazish", "kind": "service", "track_stock": 1},
            {"id": 2, "name": "Quti", "kind": "product", "track_stock": 0},
        ],
    }
    await sync_business_catalog(
        store,
        account_id=7,
        owner_name="Savdo",
        payload=payload,
        changed_resources={"items"},
    )
    await sync_business_inventory(
        store,
        account_id=7,
        payload=payload,
        changed_resources={"items"},
    )
    assert await store.scalar(select(func.count()).select_from(InventoryItem)) == 0
