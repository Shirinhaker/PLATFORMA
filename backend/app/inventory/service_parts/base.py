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
)
from app.inventory.repository import InventoryRepository
from app.inventory.service_parts.helpers import (
    EPSILON,
    QUANTITY_STEP,
    NowProvider,
    SessionFactory,
    _money_total,
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
