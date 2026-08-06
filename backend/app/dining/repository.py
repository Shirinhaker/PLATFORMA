"""Ovqatlanish domeni uchun baza so'rovlari."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.model import CatalogItem
from app.dining.model import DiningOrder, DiningOrderItem, DiningPlace
from app.inventory.model import InventoryItem


class DiningRepository:
    async def places(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
    ) -> list[DiningPlace]:
        return list((await session.scalars(
            select(DiningPlace)
            .where(DiningPlace.business_account_id == business_account_id)
            .order_by(DiningPlace.id)
        )).all())

    async def place(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        place_id: int,
        lock: bool = False,
    ) -> DiningPlace | None:
        statement = select(DiningPlace).where(
            DiningPlace.id == place_id,
            DiningPlace.business_account_id == business_account_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def order(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        order_id: int,
        lock: bool = False,
    ) -> DiningOrder | None:
        """Ichki zakazni oladi — stol bandligi (`booking`) bu yerga tushmaydi."""
        statement = select(DiningOrder).where(
            DiningOrder.id == order_id,
            DiningOrder.business_account_id == business_account_id,
            DiningOrder.kind == "order",
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def orders(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        active_only: bool = False,
    ) -> list[DiningOrder]:
        statement = select(DiningOrder).where(
            DiningOrder.business_account_id == business_account_id
        )
        if active_only:
            statement = statement.where(DiningOrder.status == "active")
        return list((await session.scalars(
            statement.order_by(DiningOrder.id.desc())
        )).all())

    async def active_orders_for_place(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        place_id: int,
        lock: bool = False,
    ) -> list[DiningOrder]:
        statement = select(DiningOrder).where(
            DiningOrder.business_account_id == business_account_id,
            DiningOrder.place_id == place_id,
            DiningOrder.status == "active",
        )
        if lock:
            statement = statement.with_for_update()
        return list((await session.scalars(
            statement.order_by(DiningOrder.id)
        )).all())

    async def items(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        lock: bool = False,
    ) -> list[DiningOrderItem]:
        statement = select(DiningOrderItem).where(
            DiningOrderItem.order_id == order_id
        )
        if lock:
            statement = statement.with_for_update()
        return list((await session.scalars(
            statement.order_by(DiningOrderItem.id)
        )).all())

    async def items_for_orders(
        self,
        session: AsyncSession,
        *,
        order_ids: Sequence[int],
    ) -> dict[int, list[DiningOrderItem]]:
        """N+1 so'rovni oldini oladi — ro'yxat ekranlari shuni ishlatadi."""
        if not order_ids:
            return {}
        rows = list((await session.scalars(
            select(DiningOrderItem)
            .where(DiningOrderItem.order_id.in_(order_ids))
            .order_by(DiningOrderItem.order_id, DiningOrderItem.id)
        )).all())
        grouped: dict[int, list[DiningOrderItem]] = {}
        for row in rows:
            grouped.setdefault(row.order_id, []).append(row)
        return grouped

    async def menu_items(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        catalog_item_ids: Sequence[int],
    ) -> list[CatalogItem]:
        """Zakazga qo'shsa bo'ladigan taomlar.

        v1656 `_dining_prepare_items` faqat `stock_type='ready_food'`
        mahsulotlarni qabul qiladi. Omborda yozuvi yo'q mahsulot ham
        tayyor taom hisoblanadi — v1656dagi `COALESCE(stock_type,
        'ready_food')` shuni bildiradi.
        """
        if not catalog_item_ids:
            return []
        return list((await session.scalars(
            select(CatalogItem)
            .outerjoin(
                InventoryItem,
                InventoryItem.catalog_item_id == CatalogItem.id,
            )
            .where(
                CatalogItem.business_account_id == business_account_id,
                CatalogItem.id.in_(catalog_item_ids),
                (
                    InventoryItem.stock_type.is_(None)
                    | (InventoryItem.stock_type == "ready_food")
                ),
            )
            .order_by(CatalogItem.id)
        )).all())
