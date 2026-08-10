from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.model import CatalogItem
from app.inventory.model import InventoryItem, StockBatch, StockMove


INVENTORY_RESOURCES = frozenset({"items"})
QUANTITY_STEP = Decimal("0.001")


async def sync_business_inventory(
    session: AsyncSession,
    *,
    account_id: int,
    payload: dict[str, Any],
    changed_resources: set[str],
) -> None:
    """Kabinet mahsulotlarini Ombor domeni bilan bitta tranzaksiyada tenglaydi."""
    if not INVENTORY_RESOURCES.intersection(changed_resources):
        return

    value = payload.get("items")
    rows = [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []
    rows_by_source = {
        str(row.get("id")): row
        for row in rows
        if row.get("id") not in (None, "")
    }
    catalog_items = list((await session.scalars(
        select(CatalogItem).where(
            CatalogItem.business_account_id == account_id,
            CatalogItem.source_record_key.is_not(None),
        )
    )).all())
    inventory_items = list((await session.scalars(
        select(InventoryItem).where(
            InventoryItem.business_account_id == account_id,
        )
    )).all())
    inventory_by_catalog = {
        item.catalog_item_id: item for item in inventory_items
    }
    now = datetime.now(UTC)

    for catalog in catalog_items:
        row = rows_by_source.get(str(catalog.source_record_key))
        if row is None:
            continue
        tracked = catalog.kind == "product" and _boolean(row.get("track_stock"))
        item = inventory_by_catalog.get(catalog.id)
        if item is None and not tracked:
            continue

        stock_type = (
            "raw_material"
            if str(row.get("stock_type") or "").strip() == "raw_material"
            else "ready_food"
        )
        min_qty = _quantity(row.get("min_qty"), minimum=Decimal("0"))
        if item is None:
            initial_qty = _quantity(row.get("stock_qty"), minimum=Decimal("0"))
            legacy_source_id = (
                int(catalog.source_record_key)
                if str(catalog.source_record_key or "").isdigit()
                else None
            )
            item = InventoryItem(
                business_account_id=account_id,
                catalog_item_id=catalog.id,
                legacy_source_id=legacy_source_id,
                track_stock=True,
                stock_type=stock_type,
                stock_qty=initial_qty,
                cost_price=0,
                min_qty=min_qty,
                fifo_initialized=True,
                created_at=now,
                updated_at=now,
            )
            session.add(item)
            await session.flush()
            inventory_by_catalog[catalog.id] = item
            if initial_qty > 0:
                move = StockMove(
                    business_account_id=account_id,
                    inventory_item_id=item.id,
                    legacy_source_id=None,
                    delta=initial_qty,
                    reason="tuzatish",
                    note="Boshlang‘ich qoldiq",
                    cost=0,
                    legacy_order_source_id=None,
                    cash_sale_line_id=None,
                    performed_by_staff_id=None,
                    created_at=now,
                )
                session.add(move)
                await session.flush()
                session.add(StockBatch(
                    business_account_id=account_id,
                    inventory_item_id=item.id,
                    legacy_source_id=None,
                    qty_in=initial_qty,
                    qty_remaining=initial_qty,
                    unit_cost=0,
                    source_move_id=move.id,
                    created_at=now,
                ))
        else:
            # Tahrirlash qoldiqni qayta yozmaydi; faqat Ombor harakati o‘zgartiradi.
            item.track_stock = tracked
            item.stock_type = stock_type
            item.min_qty = min_qty
            item.updated_at = now

    await session.flush()


def _boolean(value: object) -> bool:
    return value is True or str(value or "").strip().casefold() in {
        "1", "true", "on", "yes",
    }


def _quantity(value: object, *, minimum: Decimal) -> Decimal:
    try:
        parsed = Decimal(str(value or 0)).quantize(
            QUANTITY_STEP,
            rounding=ROUND_HALF_EVEN,
        )
    except (InvalidOperation, TypeError, ValueError):
        return minimum
    if not parsed.is_finite():
        return minimum
    return max(minimum, min(parsed, Decimal("100000")))
