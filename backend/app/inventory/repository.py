from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.model import CatalogGroup, CatalogItem
from app.inventory.model import (
    InventoryItem,
    ProductionBatch,
    ProductionInput,
    RecipeIngredient,
    StockBatch,
    StockBatchConsumption,
    StockMove,
)
from app.profiles.model import BusinessProfile
from app.staff.model import StaffMember


class InventoryRepository:
    async def business_direction(
        self,
        session: AsyncSession,
        business_account_id: int,
    ) -> str:
        value = await session.scalar(
            select(BusinessProfile.direction).where(
                BusinessProfile.account_id == business_account_id
            )
        )
        return str(value or "")

    async def catalog_item(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        catalog_item_id: int,
    ) -> CatalogItem | None:
        return await session.scalar(
            select(CatalogItem).where(
                CatalogItem.id == catalog_item_id,
                CatalogItem.business_account_id == business_account_id,
            )
        )

    async def inventory_item_by_catalog(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        catalog_item_id: int,
        lock: bool = False,
    ) -> InventoryItem | None:
        statement = select(InventoryItem).where(
            InventoryItem.business_account_id == business_account_id,
            InventoryItem.catalog_item_id == catalog_item_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def owned_item(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        inventory_item_id: int,
        lock: bool = False,
    ) -> tuple[InventoryItem, CatalogItem] | None:
        statement = (
            select(InventoryItem, CatalogItem)
            .join(CatalogItem, CatalogItem.id == InventoryItem.catalog_item_id)
            .where(
                InventoryItem.id == inventory_item_id,
                InventoryItem.business_account_id == business_account_id,
                CatalogItem.business_account_id == business_account_id,
            )
        )
        if lock:
            statement = statement.with_for_update(of=InventoryItem)
        row = (await session.execute(statement)).first()
        return (row[0], row[1]) if row is not None else None

    async def list_items(
        self,
        session: AsyncSession,
        business_account_id: int,
    ):
        fifo_next = (
            select(StockBatch.unit_cost)
            .where(
                StockBatch.inventory_item_id == InventoryItem.id,
                StockBatch.qty_remaining > 0,
            )
            .order_by(StockBatch.created_at, StockBatch.id)
            .limit(1)
            .correlate(InventoryItem)
            .scalar_subquery()
        )
        fifo_value = (
            select(func.coalesce(func.sum(
                StockBatch.qty_remaining * StockBatch.unit_cost
            ), 0))
            .where(
                StockBatch.inventory_item_id == InventoryItem.id,
                StockBatch.qty_remaining > 0,
            )
            .correlate(InventoryItem)
            .scalar_subquery()
        )
        statement = (
            select(
                InventoryItem,
                CatalogItem,
                CatalogGroup.name.label("group_name"),
                func.coalesce(fifo_next, 0).label("fifo_next_cost"),
                func.coalesce(fifo_value, 0).label("fifo_value"),
            )
            .join(CatalogItem, CatalogItem.id == InventoryItem.catalog_item_id)
            .outerjoin(CatalogGroup, CatalogGroup.id == CatalogItem.catalog_group_id)
            .where(
                InventoryItem.business_account_id == business_account_id,
                InventoryItem.track_stock.is_(True),
            )
            .order_by(func.lower(CatalogItem.name), InventoryItem.id)
        )
        return (await session.execute(statement)).all()

    async def fifo_batches(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        inventory_item_id: int,
        lock: bool,
    ) -> list[StockBatch]:
        statement = (
            select(StockBatch)
            .where(
                StockBatch.business_account_id == business_account_id,
                StockBatch.inventory_item_id == inventory_item_id,
                StockBatch.qty_remaining > 0,
            )
            .order_by(StockBatch.created_at, StockBatch.id)
        )
        if lock:
            statement = statement.with_for_update()
        return list((await session.scalars(statement)).all())

    async def move(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        move_id: int,
        lock: bool = False,
    ) -> StockMove | None:
        statement = select(StockMove).where(
            StockMove.id == move_id,
            StockMove.business_account_id == business_account_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def source_batch(
        self,
        session: AsyncSession,
        move_id: int,
        *,
        lock: bool,
    ) -> StockBatch | None:
        statement = select(StockBatch).where(StockBatch.source_move_id == move_id)
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def consumptions(
        self,
        session: AsyncSession,
        *,
        source_type: str,
        source_id: int,
        lock: bool,
    ) -> list[StockBatchConsumption]:
        statement = (
            select(StockBatchConsumption)
            .where(
                StockBatchConsumption.source_type == source_type,
                StockBatchConsumption.source_id == source_id,
            )
            .order_by(StockBatchConsumption.id.desc())
        )
        if lock:
            statement = statement.with_for_update()
        return list((await session.scalars(statement)).all())

    async def delete_consumptions(
        self,
        session: AsyncSession,
        *,
        source_type: str,
        source_id: int,
    ) -> None:
        await session.execute(
            delete(StockBatchConsumption).where(
                StockBatchConsumption.source_type == source_type,
                StockBatchConsumption.source_id == source_id,
            )
        )

    async def replace_recipe(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        ready_inventory_item_id: int,
        rows: list[RecipeIngredient],
    ) -> None:
        await session.execute(
            delete(RecipeIngredient).where(
                RecipeIngredient.business_account_id == business_account_id,
                RecipeIngredient.ready_inventory_item_id == ready_inventory_item_id,
            )
        )
        session.add_all(rows)

    async def recipe_rows(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        ready_inventory_item_id: int,
    ):
        statement = (
            select(RecipeIngredient, InventoryItem, CatalogItem)
            .join(
                InventoryItem,
                InventoryItem.id == RecipeIngredient.ingredient_inventory_item_id,
            )
            .join(CatalogItem, CatalogItem.id == InventoryItem.catalog_item_id)
            .where(
                RecipeIngredient.business_account_id == business_account_id,
                RecipeIngredient.ready_inventory_item_id == ready_inventory_item_id,
            )
            .order_by(func.lower(CatalogItem.name), RecipeIngredient.id)
        )
        return (await session.execute(statement)).all()

    async def move_rows(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        inventory_item_id: int,
        limit: int,
    ):
        statement = (
            select(StockMove, StaffMember.name.label("staff_name"))
            .outerjoin(StaffMember, StaffMember.id == StockMove.performed_by_staff_id)
            .where(
                StockMove.business_account_id == business_account_id,
                StockMove.inventory_item_id == inventory_item_id,
            )
            .order_by(StockMove.created_at.desc(), StockMove.id.desc())
            .limit(limit)
        )
        return (await session.execute(statement)).all()

    async def production_rows(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        limit: int,
    ):
        ready_item = InventoryItem.__table__.alias("ready_inventory_item")
        ready_catalog = CatalogItem.__table__.alias("ready_catalog_item")
        statement = (
            select(
                ProductionBatch,
                ready_catalog.c.name.label("ready_name"),
                ready_catalog.c.unit.label("ready_unit"),
                StaffMember.name.label("staff_name"),
            )
            .join(ready_item, ready_item.c.id == ProductionBatch.ready_inventory_item_id)
            .join(ready_catalog, ready_catalog.c.id == ready_item.c.catalog_item_id)
            .outerjoin(StaffMember, StaffMember.id == ProductionBatch.performed_by_staff_id)
            .where(ProductionBatch.business_account_id == business_account_id)
            .order_by(ProductionBatch.created_at.desc(), ProductionBatch.id.desc())
            .limit(limit)
        )
        return (await session.execute(statement)).all()

    async def production_input_rows(
        self,
        session: AsyncSession,
        production_batch_ids: list[int],
    ):
        if not production_batch_ids:
            return []
        statement = (
            select(ProductionInput, CatalogItem.name, CatalogItem.unit)
            .join(InventoryItem, InventoryItem.id == ProductionInput.inventory_item_id)
            .join(CatalogItem, CatalogItem.id == InventoryItem.catalog_item_id)
            .where(ProductionInput.production_batch_id.in_(production_batch_ids))
            .order_by(ProductionInput.production_batch_id, ProductionInput.id)
        )
        return (await session.execute(statement)).all()
