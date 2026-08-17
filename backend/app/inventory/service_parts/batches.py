"""Ombor partiyalari: kirim yozuvi va ishlab chiqarish xomashyosi.

Bu yordamchilar `moves.py` ni 500 qatordan oshirib yuborgan edi.
Ular alohida mavzu — partiya bilan ishlash — shuning uchun o'z
modulida. `MovesMixin` shundan meros oladi, chaqiruvlar o'zgarmaydi.
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.inventory.model import (
    InventoryItem,
    StockBatch,
)
from app.inventory.schemas import (
    StockMoveCreate,
)
from app.inventory.service_parts.helpers import (
    FRACTIONAL_UNITS,
    QUANTITY_STEP,
    _quantity,
)


class BatchesMixin:
    async def _production_inputs(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        body: StockMoveCreate,
        ready_item: InventoryItem,
        direction: str,
    ):
        if body.ingredients and body.delta <= 0:
            raise ApiError(
                422,
                "inventory_production_delta_invalid",
                "Ishlab chiqarishda tayyor mahsulot miqdori musbat bo‘lsin.",
            )
        if body.ingredients and ready_item.stock_type != "ready_food":
            raise ApiError(
                422,
                "inventory_production_target_invalid",
                "Xomashyo faqat tayyor taom kirimida sarflanadi.",
            )
        if not body.ingredients:
            if (
                body.delta > 0
                and ready_item.stock_type == "ready_food"
                and direction == "Umumiy ovqatlanish"
            ):
                raise ApiError(
                    422,
                    "inventory_production_inputs_required",
                    "Tayyor taom kirimi uchun sarflangan mahsulotlarni kiriting.",
                )
            return []
        quantities: dict[int, Decimal] = {}
        for row in body.ingredients:
            if row.item_id in quantities:
                raise ApiError(
                    422,
                    "inventory_ingredient_duplicate",
                    "Bir xomashyo retseptda bir marta kiritiladi.",
                )
            quantities[row.item_id] = _quantity(row.qty)
        result = []
        for item_id in sorted(quantities):
            owned = await self._repository.owned_item(
                session,
                business_account_id=business_account_id,
                inventory_item_id=item_id,
                lock=True,
            )
            if (
                owned is None
                or not owned[0].track_stock
                or owned[0].stock_type != "raw_material"
            ):
                raise ApiError(
                    422,
                    "inventory_ingredient_invalid",
                    "Sarflangan xomashyo noto‘g‘ri tanlangan.",
                )
            qty = self._unit_quantity(quantities[item_id], owned[1].unit)
            if qty <= 0:
                raise ApiError(422, "inventory_quantity_invalid", "Miqdor noto‘g‘ri.")
            result.append((owned[0], owned[1], qty))
        return result

    @staticmethod
    def _add_batch(
        session: AsyncSession,
        *,
        business_account_id: int,
        item: InventoryItem,
        qty: Decimal,
        unit_cost: int,
        source_move_id: int,
        now: datetime,
    ) -> None:
        session.add(
            StockBatch(
                business_account_id=business_account_id,
                inventory_item_id=item.id,
                legacy_source_id=None,
                qty_in=qty,
                qty_remaining=qty,
                unit_cost=max(0, unit_cost),
                source_move_id=source_move_id,
                created_at=now,
            )
        )
        item.fifo_initialized = True

    @staticmethod
    def _unit_quantity(value: object, unit: str) -> Decimal:
        quantity = _quantity(value)
        if (unit or "dona") not in FRACTIONAL_UNITS:
            sign = Decimal("1") if quantity > 0 else Decimal("-1")
            quantity = sign * abs(quantity).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
            quantity = quantity.quantize(QUANTITY_STEP)
        return quantity
