"""Kassa savdosi bilan bog'liq yechish va qaytarish."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.inventory.model import (
    StockMove,
)
from app.inventory.service_parts.base import InventoryServiceBase
from app.inventory.service_parts.helpers import (
    EPSILON,
    _money_per_unit,
    _quantity,
)


class CashLinesMixin(InventoryServiceBase):
    async def lock_cash_catalog_items(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        catalog_item_ids: list[int],
    ) -> None:
        """Parallel cheklar bir xil Ombor yozuvlarini doim bir tartibda qulflaydi."""
        for catalog_item_id in sorted(set(catalog_item_ids)):
            await self._repository.inventory_item_by_catalog(
                session,
                business_account_id=business_account_id,
                catalog_item_id=catalog_item_id,
                lock=True,
            )

    async def consume_cash_line(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        catalog_item_id: int,
        cash_sale_line_id: int,
        qty: Decimal,
        actor_staff_id: int | None,
        note: str,
        now: datetime,
    ) -> tuple[int | None, int]:
        """Kassa qatorini FIFO bilan sarflaydi; commit tashqi tranzaksiyaga tegishli."""
        item = await self._repository.inventory_item_by_catalog(
            session,
            business_account_id=business_account_id,
            catalog_item_id=catalog_item_id,
            lock=True,
        )
        if item is None or not item.track_stock:
            return None, 0
        quantity = _quantity(qty)
        if quantity <= 0:
            raise ApiError(422, "inventory_quantity_invalid", "Miqdor noto‘g‘ri.")
        total_cost = await self._consume_fifo(
            session,
            business_account_id=business_account_id,
            item=item,
            qty=quantity,
            source_type="cash_line",
            source_id=cash_sale_line_id,
            now=now,
            require_cost=False,
        )
        item.stock_qty = _quantity(item.stock_qty - quantity)
        item.updated_at = now
        session.add(
            StockMove(
                business_account_id=business_account_id,
                inventory_item_id=item.id,
                legacy_source_id=None,
                delta=-quantity,
                reason="sotuv",
                note=note[:200],
                cost=_money_per_unit(total_cost, quantity),
                legacy_order_source_id=None,
                cash_sale_line_id=cash_sale_line_id,
                performed_by_staff_id=actor_staff_id,
                created_at=now,
            )
        )
        return item.id, total_cost

    async def restore_cash_line(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        inventory_item_id: int,
        cash_sale_line_id: int,
        qty: Decimal,
        actor_staff_id: int | None,
        note: str,
        now: datetime,
    ) -> None:
        """O‘chirilayotgan chek qatorining FIFO sarfini aynan qaytaradi."""
        owned = await self._repository.owned_item(
            session,
            business_account_id=business_account_id,
            inventory_item_id=inventory_item_id,
            lock=True,
        )
        if owned is None:
            raise ApiError(
                409,
                "inventory_cash_restore_failed",
                "Chek ombori topilmadi; savdo o‘chirilmadi.",
            )
        item, _catalog = owned
        quantity = _quantity(qty)
        restored = await self._restore_fifo(
            session,
            source_type="cash_line",
            source_id=cash_sale_line_id,
        )
        if abs(restored - quantity) > EPSILON:
            raise ApiError(
                409,
                "inventory_cash_restore_incomplete",
                "Chekning FIFO sarfi to‘liq topilmadi; savdo o‘chirilmadi.",
            )
        item.stock_qty = _quantity(item.stock_qty + quantity)
        item.updated_at = now
        session.add(
            StockMove(
                business_account_id=business_account_id,
                inventory_item_id=item.id,
                legacy_source_id=None,
                delta=quantity,
                reason="tuzatish",
                note=note[:200],
                cost=0,
                legacy_order_source_id=None,
                cash_sale_line_id=None,
                performed_by_staff_id=actor_staff_id,
                created_at=now,
            )
        )
