"""Ombor mahsulotlari: ro'yxat va sozlash."""

from __future__ import annotations

from decimal import Decimal

from app.core.errors import ApiError
from app.inventory.model import (
    InventoryItem,
)
from app.inventory.schemas import (
    InventoryItemRead,
    InventoryItemWrite,
    InventoryListRead,
)
from app.inventory.service_parts.base import InventoryServiceBase
from app.inventory.service_parts.helpers import (
    _number,
    _quantity,
)


class ItemsMixin(InventoryServiceBase):
    async def list_items(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
    ) -> InventoryListRead:
        self._require_any(permissions, "ombor", "production")
        show_costs = self._can_view_costs(permissions)
        async with self._session_factory() as session:
            rows = await self._repository.list_items(session, business_account_id)
            result = InventoryListRead(
                items=[self._item_read(row, show_costs=show_costs) for row in rows]
            )
            await session.rollback()
            return result

    async def configure_item(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        catalog_item_id: int,
        body: InventoryItemWrite,
    ) -> InventoryItemRead:
        self._require_any(permissions, "ombor")
        async with self._session_factory() as session:
            catalog = await self._repository.catalog_item(
                session,
                business_account_id=business_account_id,
                catalog_item_id=catalog_item_id,
            )
            if catalog is None:
                raise ApiError(
                    404,
                    "catalog_item_not_found",
                    "Mahsulot topilmadi.",
                )
            item = await self._repository.inventory_item_by_catalog(
                session,
                business_account_id=business_account_id,
                catalog_item_id=catalog_item_id,
                lock=True,
            )
            now = self._now_provider()
            if item is None:
                legacy_source_id = (
                    int(catalog.source_record_key)
                    if str(catalog.source_record_key or "").isdigit()
                    else None
                )
                item = InventoryItem(
                    business_account_id=business_account_id,
                    catalog_item_id=catalog.id,
                    legacy_source_id=legacy_source_id,
                    track_stock=body.track_stock,
                    stock_type=body.stock_type,
                    stock_qty=Decimal("0"),
                    cost_price=0,
                    min_qty=_quantity(body.min_qty),
                    fifo_initialized=True,
                    created_at=now,
                    updated_at=now,
                )
                session.add(item)
            else:
                item.track_stock = body.track_stock
                item.stock_type = body.stock_type
                item.min_qty = _quantity(body.min_qty)
                item.updated_at = now
            await session.flush()
            await session.commit()
            return InventoryItemRead(
                id=item.id,
                catalog_item_id=catalog.id,
                name=catalog.name,
                price=catalog.price_text,
                unit=catalog.unit or "dona",
                stock_qty=_number(item.stock_qty),
                cost_price=item.cost_price if self._can_view_costs(permissions) else 0,
                fifo_next_cost=0,
                fifo_value=0,
                min_qty=_number(item.min_qty),
                image_url="",
                group_id=catalog.catalog_group_id,
                group_name="",
                stock_type=item.stock_type,
                low_stock=item.stock_qty <= item.min_qty,
            )

    @staticmethod
    def _item_read(row, *, show_costs: bool) -> InventoryItemRead:
        item, catalog, group_name, fifo_next_cost, fifo_value = row
        return InventoryItemRead(
            id=item.id,
            catalog_item_id=catalog.id,
            name=catalog.name,
            price=catalog.price_text if show_costs else "",
            unit=catalog.unit or "dona",
            stock_qty=_number(item.stock_qty),
            cost_price=item.cost_price if show_costs else 0,
            fifo_next_cost=int(fifo_next_cost or 0) if show_costs else 0,
            fifo_value=round(float(fifo_value or 0)) if show_costs else 0,
            min_qty=_number(item.min_qty),
            image_url="",
            group_id=catalog.catalog_group_id,
            group_name=str(group_name or ""),
            stock_type=item.stock_type,
            low_stock=item.stock_qty <= item.min_qty,
        )
