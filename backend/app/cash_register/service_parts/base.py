"""Umumiy asos: kun chegarasi, kassa huquqi, chek shakli."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from app.cash_register.model import CashReceipt, CashReceiptLine
from app.cash_register.repository import CashRegisterRepository
from app.cash_register.schemas import (
    CashReceiptLineRead,
    CashReceiptRead,
)
from app.cash_register.service_parts.helpers import (
    PAY_TEXT,
    UZBEKISTAN_TZ,
    NowProvider,
    SessionFactory,
)
from app.core.errors import ApiError
from app.debt_ledger.service import DebtLedgerService
from app.inventory.service_parts import InventoryService


class CashRegisterServiceBase:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: CashRegisterRepository | None = None,
        inventory_service: InventoryService | None = None,
        debt_ledger_service: DebtLedgerService | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or CashRegisterRepository()
        self._inventory = inventory_service or InventoryService(session_factory)
        self._debt_ledger = debt_ledger_service
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    def _day_bounds(self, value: date | None) -> tuple[date, datetime, datetime]:
        local_now = self._now_provider().astimezone(UZBEKISTAN_TZ)
        selected = value or local_now.date()
        local_start = datetime.combine(selected, time.min, tzinfo=UZBEKISTAN_TZ)
        start = local_start.astimezone(UTC)
        return selected, start, start + timedelta(days=1)

    def _sale_time(self, value: date | None) -> datetime:
        now = self._now_provider()
        today = now.astimezone(UZBEKISTAN_TZ).date()
        if value is None or value == today:
            return now
        if value > today:
            raise ApiError(
                422,
                "cash_future_date_forbidden",
                "Kelajak sanaga savdo yozib bo‘lmaydi.",
            )
        return datetime.combine(value, time(hour=12), tzinfo=UZBEKISTAN_TZ).astimezone(
            UTC
        )

    @staticmethod
    def _require_kassa(permissions: tuple[str, ...] | None) -> None:
        if permissions is not None and "kassa" not in permissions:
            raise ApiError(
                403,
                "staff_permission_required",
                "Bu bo‘limga vakolatingiz yo‘q.",
            )

    @staticmethod
    def _receipt_read(
        receipt: CashReceipt,
        lines: list[CashReceiptLine],
        *,
        staff_name: str,
        show_costs: bool,
    ) -> CashReceiptRead:
        return CashReceiptRead(
            id=receipt.id,
            receipt_no=receipt.receipt_no,
            source=receipt.source,
            order_id=receipt.order_id or receipt.legacy_order_source_id,
            pay_type=receipt.pay_type,
            pay_text=(
                "Qarz to‘lovi"
                if receipt.source == "debt_payment"
                else PAY_TEXT.get(receipt.pay_type, receipt.pay_type)
            ),
            debtor_name=receipt.debtor_name_snapshot,
            note=receipt.note,
            who=staff_name or receipt.actor_name_snapshot or "Rahbar",
            created_at=receipt.created_at,
            total=sum(line.total for line in lines),
            can_delete=(receipt.source in {"manual", "debt_payment"}),
            can_change_payment=receipt.source == "order",
            lines=[
                CashReceiptLineRead(
                    id=line.id,
                    catalog_item_id=line.catalog_item_id,
                    item_name=line.item_name,
                    qty=float(line.qty),
                    unit=line.unit,
                    price=line.unit_price,
                    total=line.total,
                    cost_total=line.cost_total if show_costs else 0,
                )
                for line in lines
            ],
        )
