"""Umumiy asos: FIFO yechish/qaytarish, huquq, javob shakli.

`_consume_fifo` va `_restore_fifo` — omborning yuragi: partiyalar
kelgan tartibda yechiladi, bekor qilinganda o'sha tartibda qaytadi.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.expenses.service import ExpenseService
from app.inventory.model import (
    InventoryItem,
    StockBatch,
    StockBatchConsumption,
    StockMove,
)
from app.inventory.repository import InventoryRepository
from app.inventory.schemas import (
    InventoryItemRead,
    StockMoveCreate,
)
from app.inventory.service_parts.helpers import (
    EPSILON,
    FRACTIONAL_UNITS,
    QUANTITY_STEP,
    NowProvider,
    SessionFactory,
    _money_total,
    _number,
    _quantity,
)


class InventoryServiceBase:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: InventoryRepository | None = None,
        expense_service: ExpenseService | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or InventoryRepository()
        self._expenses = expense_service or ExpenseService(session_factory)
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

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

    async def _consume_fifo(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        item: InventoryItem,
        qty: Decimal,
        source_type: str,
        source_id: int,
        now: datetime,
        require_cost: bool,
    ) -> int:
        batches = await self._repository.fifo_batches(
            session,
            business_account_id=business_account_id,
            inventory_item_id=item.id,
            lock=True,
        )
        available = sum((batch.qty_remaining for batch in batches), Decimal("0"))
        if available + EPSILON < qty:
            raise ApiError(
                409,
                "inventory_fifo_insufficient",
                "FIFO partiyalarida qoldiq yetarli emas.",
            )
        left = qty
        for batch in batches:
            take = min(left, batch.qty_remaining)
            if take > 0 and require_cost and batch.unit_cost <= 0:
                raise ApiError(
                    409,
                    "inventory_fifo_cost_required",
                    "Eng eski FIFO partiyasida tannarx kiritilmagan.",
                )
            left -= take
            if left <= EPSILON:
                break
        left = qty
        total = 0
        for batch in batches:
            if left <= EPSILON:
                break
            take = min(left, batch.qty_remaining).quantize(
                QUANTITY_STEP, rounding=ROUND_HALF_UP
            )
            line_total = _money_total(batch.unit_cost, take)
            total += line_total
            batch.qty_remaining = _quantity(batch.qty_remaining - take)
            session.add(
                StockBatchConsumption(
                    batch_id=batch.id,
                    inventory_item_id=item.id,
                    legacy_source_id=None,
                    qty=take,
                    unit_cost=batch.unit_cost,
                    total_cost=line_total,
                    source_type=source_type,
                    source_id=source_id,
                    created_at=now,
                )
            )
            left = _quantity(left - take)
        return total

    async def _restore_fifo(
        self,
        session: AsyncSession,
        *,
        source_type: str,
        source_id: int,
    ) -> Decimal:
        rows = await self._repository.consumptions(
            session,
            source_type=source_type,
            source_id=source_id,
            lock=True,
        )
        batch_ids = sorted({row.batch_id for row in rows})
        batches = {}
        for batch_id in batch_ids:
            batch = await session.get(StockBatch, batch_id, with_for_update=True)
            if batch is None:
                raise ApiError(
                    409,
                    "inventory_fifo_restore_failed",
                    "FIFO partiyasi topilmadi; harakat qaytarilmadi.",
                )
            batches[batch_id] = batch
        for row in rows:
            batch = batches[row.batch_id]
            batch.qty_remaining = _quantity(batch.qty_remaining + row.qty)
        restored = sum((row.qty for row in rows), Decimal("0"))
        await self._repository.delete_consumptions(
            session,
            source_type=source_type,
            source_id=source_id,
        )
        return restored

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

    @staticmethod
    def _move_deletable(move: StockMove) -> bool:
        if move.legacy_order_source_id is not None:
            return False
        if move.reason not in {"kirim", "chiqim"}:
            return False
        return not move.note.startswith(("Kassa", "Chek", "Ishlab chiqarish"))

    @staticmethod
    def _require_any(
        permissions: tuple[str, ...] | None,
        *allowed: str,
    ) -> None:
        if permissions is None:
            return
        if not set(permissions).intersection(allowed):
            raise ApiError(
                403,
                "staff_permission_required",
                "Bu bo‘limga vakolatingiz yo‘q.",
            )

    @staticmethod
    def _can_view_costs(permissions: tuple[str, ...] | None) -> bool:
        return permissions is None or bool(
            {"expenses", "statistics"}.intersection(permissions)
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
            fifo_value=int(round(float(fifo_value or 0))) if show_costs else 0,
            min_qty=_number(item.min_qty),
            image_url="",
            group_id=catalog.catalog_group_id,
            group_name=str(group_name or ""),
            stock_type=item.stock_type,
            low_stock=item.stock_qty <= item.min_qty,
        )
