from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
import re
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cash_register.model import CashReceipt, CashReceiptLine
from app.cash_register.repository import CashRegisterRepository
from app.cash_register.schemas import (
    CashCatalogItemRead,
    CashPaymentUpdate,
    CashReceiptCreate,
    CashReceiptCreated,
    CashReceiptLineRead,
    CashReceiptRead,
    CashRegisterRead,
    CashTotalsRead,
)
from app.core.errors import ApiError
from app.inventory.service import InventoryService
from app.orders.model import Order, OrderItem


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NowProvider = Callable[[], datetime]
UZBEKISTAN_TZ = ZoneInfo("Asia/Tashkent")
FRACTIONAL_UNITS = frozenset({"kg", "g", "l", "litr", "ml", "metr", "sm", "m²", "m3", "soat"})
QUANTITY_STEP = Decimal("0.001")
PAY_TEXT = {
    "": "Buyurtma",
    "naqd": "Naqd",
    "karta": "Karta",
    "qarz": "Qarz",
}


def _quantity(value: object, unit: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except Exception as exc:
        raise ApiError(422, "cash_quantity_invalid", "Miqdor noto‘g‘ri.") from exc
    if not parsed.is_finite() or parsed <= 0 or parsed > Decimal("100000"):
        raise ApiError(422, "cash_quantity_invalid", "Miqdor noto‘g‘ri.")
    if (unit or "dona") not in FRACTIONAL_UNITS:
        parsed = parsed.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        parsed = max(Decimal("1"), parsed)
    return parsed.quantize(QUANTITY_STEP, rounding=ROUND_HALF_EVEN)


def _money_total(price: int, qty: Decimal) -> int:
    return int((Decimal(price) * qty).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def _price(value: str) -> int:
    digits = re.sub(r"[^0-9]", "", value or "")
    return int(digits[:12]) if digits else 0


class CashRegisterService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: CashRegisterRepository | None = None,
        inventory_service: InventoryService | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or CashRegisterRepository()
        self._inventory = inventory_service or InventoryService(session_factory)
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def catalog(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
    ) -> list[CashCatalogItemRead]:
        self._require_kassa(permissions)
        async with self._session_factory() as session:
            rows = await self._repository.catalog_rows(
                session,
                business_account_id=business_account_id,
            )
            result = [
                CashCatalogItemRead(
                    id=catalog.id,
                    name=catalog.name,
                    price=_price(catalog.price_text),
                    price_text=catalog.price_text,
                    unit=catalog.unit or "dona",
                    track_stock=bool(inventory and inventory.track_stock),
                    stock_qty=float(inventory.stock_qty if inventory else 0),
                    low_stock=bool(
                        inventory
                        and inventory.track_stock
                        and inventory.stock_qty <= inventory.min_qty
                    ),
                )
                for catalog, inventory in rows
            ]
            await session.rollback()
            return result

    async def list_receipts(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        day: date | None,
    ) -> CashRegisterRead:
        self._require_kassa(permissions)
        selected_day, start, end = self._day_bounds(day)
        show_costs = permissions is None or bool(
            {"expenses", "statistics", "reports"}.intersection(permissions)
        )
        async with self._session_factory() as session:
            receipt_rows = await self._repository.receipt_rows(
                session,
                business_account_id=business_account_id,
                start=start,
                end=end,
            )
            receipts = [row[0] for row in receipt_rows]
            lines_by_receipt = await self._repository.lines_for_receipts(
                session,
                [receipt.id for receipt in receipts],
            )
            totals = CashTotalsRead()
            output: list[CashReceiptRead] = []
            for (receipt, staff_name) in receipt_rows:
                lines = lines_by_receipt.get(receipt.id, [])
                total = sum(line.total for line in lines)
                totals.all += total
                if receipt.source == "debt_payment":
                    totals.qarzpay += total
                    totals.cash_in += total
                elif receipt.pay_type in {"naqd", "karta", "qarz"}:
                    setattr(
                        totals,
                        receipt.pay_type,
                        getattr(totals, receipt.pay_type) + total,
                    )
                    if receipt.pay_type in {"naqd", "karta"}:
                        totals.cash_in += total
                else:
                    totals.order += total
                output.append(self._receipt_read(
                    receipt,
                    lines,
                    staff_name=str(staff_name or ""),
                    show_costs=show_costs,
                ))
            await session.rollback()
            return CashRegisterRead(
                day=selected_day,
                totals=totals,
                receipts=output,
            )

    async def create_receipt(
        self,
        *,
        business_account_id: int,
        actor_staff_id: int | None,
        actor_name: str,
        permissions: tuple[str, ...] | None,
        body: CashReceiptCreate,
    ) -> CashReceiptCreated:
        self._require_kassa(permissions)
        if body.pay_type == "qarz":
            raise ApiError(
                409,
                "cash_debt_module_required",
                "Qarzga savdo Qarz daftari migratsiyasidan keyin yoqiladi.",
            )
        now = self._sale_time(body.sale_date)
        async with self._session_factory() as session:
            try:
                requested = sorted({
                    item.catalog_item_id
                    for item in body.items
                    if item.catalog_item_id is not None
                })
                catalog_rows = await self._repository.catalog_rows(
                    session,
                    business_account_id=business_account_id,
                    catalog_item_ids=requested,
                )
                catalogs = {row[0].id: row[0] for row in catalog_rows}
                if len(catalogs) != len(requested):
                    raise ApiError(404, "cash_catalog_item_not_found", "Mahsulot topilmadi.")
                await self._inventory.lock_cash_catalog_items(
                    session,
                    business_account_id=business_account_id,
                    catalog_item_ids=requested,
                )
                prepared = []
                for item in body.items:
                    catalog = catalogs.get(item.catalog_item_id)
                    name = catalog.name if catalog is not None else item.name
                    if not name:
                        raise ApiError(
                            422,
                            "cash_item_name_required",
                            "Mahsulot nomi kiritilmadi.",
                        )
                    unit = (catalog.unit if catalog is not None else "dona") or "dona"
                    qty = _quantity(item.qty, unit)
                    total = _money_total(item.price, qty)
                    if total <= 0:
                        raise ApiError(
                            422,
                            "cash_price_required",
                            f"Narx kiritilmadi: {name}",
                        )
                    prepared.append((catalog, name[:220], unit[:40], qty, item.price, total))

                receipt_no = await self._repository.next_receipt_no(
                    session,
                    business_account_id=business_account_id,
                    now=now,
                )
                receipt = CashReceipt(
                    business_account_id=business_account_id,
                    receipt_no=receipt_no,
                    source="manual",
                    order_id=None,
                    legacy_order_source_id=None,
                    legacy_group_key=None,
                    pay_type=body.pay_type,
                    debtor_name_snapshot="",
                    legacy_debtor_source_id=None,
                    note=body.note,
                    created_by_staff_id=actor_staff_id,
                    actor_name_snapshot=actor_name[:160],
                    created_at=now,
                )
                session.add(receipt)
                await session.flush()
                grand_total = 0
                for catalog, name, unit, qty, price, total in prepared:
                    line = CashReceiptLine(
                        receipt_id=receipt.id,
                        business_account_id=business_account_id,
                        catalog_item_id=catalog.id if catalog is not None else None,
                        inventory_item_id=None,
                        legacy_source_key=None,
                        item_name=name,
                        qty=qty,
                        unit=unit,
                        unit_price=price,
                        total=total,
                        cost_total=0,
                        created_at=now,
                    )
                    session.add(line)
                    await session.flush()
                    if catalog is not None:
                        inventory_id, cost_total = await self._inventory.consume_cash_line(
                            session,
                            business_account_id=business_account_id,
                            catalog_item_id=catalog.id,
                            cash_sale_line_id=line.id,
                            qty=qty,
                            actor_staff_id=actor_staff_id,
                            note=f"Chek #{receipt_no}",
                            now=now,
                        )
                        line.inventory_item_id = inventory_id
                        line.cost_total = cost_total
                    grand_total += total
                await session.flush()
                await session.commit()
                return CashReceiptCreated(
                    id=receipt.id,
                    receipt_no=receipt_no,
                    count=len(prepared),
                    total=grand_total,
                )
            except Exception:
                await session.rollback()
                raise

    async def delete_receipt(
        self,
        *,
        business_account_id: int,
        actor_staff_id: int | None,
        permissions: tuple[str, ...] | None,
        receipt_id: int,
    ) -> None:
        self._require_kassa(permissions)
        async with self._session_factory() as session:
            try:
                receipt = await self._repository.receipt(
                    session,
                    business_account_id=business_account_id,
                    receipt_id=receipt_id,
                    lock=True,
                )
                if receipt is None:
                    raise ApiError(404, "cash_receipt_not_found", "Chek topilmadi.")
                if receipt.source not in {"manual", "debt_payment"}:
                    raise ApiError(
                        409,
                        "cash_order_receipt_locked",
                        "Buyurtma orqali kelgan savdo bu yerdan o‘chirilmaydi.",
                    )
                if receipt.pay_type == "qarz":
                    raise ApiError(
                        409,
                        "cash_debt_receipt_locked",
                        "Qarzli chek Qarz daftari bilan birga qaytarilishi kerak.",
                    )
                lines = await self._repository.receipt_lines(
                    session, receipt.id, lock=True
                )
                now = self._now_provider()
                for line in lines:
                    if line.inventory_item_id is None:
                        continue
                    await self._inventory.restore_cash_line(
                        session,
                        business_account_id=business_account_id,
                        inventory_item_id=line.inventory_item_id,
                        cash_sale_line_id=line.id,
                        qty=line.qty,
                        actor_staff_id=actor_staff_id,
                        note=(
                            f"Chek #{receipt.receipt_no} o‘chirildi"
                            if receipt.receipt_no is not None
                            else f"Kassa #{receipt.id} o‘chirildi"
                        ),
                        now=now,
                    )
                await session.delete(receipt)
                await session.flush()
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def update_order_payment(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        receipt_id: int,
        body: CashPaymentUpdate,
    ) -> CashReceiptRead:
        self._require_kassa(permissions)
        if body.pay_type == "qarz":
            raise ApiError(
                409,
                "cash_debt_module_required",
                "Qarzga savdo Qarz daftari migratsiyasidan keyin yoqiladi.",
            )
        async with self._session_factory() as session:
            try:
                receipt = await self._repository.receipt(
                    session,
                    business_account_id=business_account_id,
                    receipt_id=receipt_id,
                    lock=True,
                )
                if receipt is None:
                    raise ApiError(404, "cash_receipt_not_found", "Savdo topilmadi.")
                if receipt.source != "order" or receipt.order_id is None:
                    raise ApiError(
                        409,
                        "cash_order_receipt_required",
                        "Bu faqat buyurtma savdosi uchun.",
                    )
                receipt.pay_type = body.pay_type
                order = await session.get(Order, receipt.order_id, with_for_update=True)
                if order is not None:
                    order.pay_type = body.pay_type
                    order.updated_at = self._now_provider()
                lines = await self._repository.receipt_lines(session, receipt.id)
                await session.commit()
                return self._receipt_read(
                    receipt,
                    lines,
                    staff_name="",
                    show_costs=permissions is None,
                )
            except Exception:
                await session.rollback()
                raise

    async def post_order(
        self,
        session: AsyncSession,
        *,
        order: Order,
        actor_staff_id: int | None,
        actor_name: str = "",
    ) -> CashReceipt | None:
        """Buyurtma topshirilganda Kassa va Omborni tashqi tranzaksiyada yozadi."""
        if order.provider_kind != "business":
            return None
        existing = await self._repository.receipt_by_order(session, order.id, lock=True)
        if existing is not None:
            return existing
        order_items = list((await session.scalars(
            select(OrderItem)
            .where(OrderItem.order_id == order.id)
            .order_by(OrderItem.id)
        )).all())
        if not order_items:
            return None
        await self._inventory.lock_cash_catalog_items(
            session,
            business_account_id=order.provider_account_id,
            catalog_item_ids=[
                item.catalog_item_id
                for item in order_items
                if item.catalog_item_id is not None
            ],
        )
        now = self._now_provider()
        receipt = CashReceipt(
            business_account_id=order.provider_account_id,
            receipt_no=None,
            source="order",
            order_id=order.id,
            legacy_order_source_id=order.legacy_source_id,
            legacy_group_key=None,
            pay_type=order.pay_type,
            debtor_name_snapshot="",
            legacy_debtor_source_id=None,
            note=f"Buyurtma #{order.id}",
            created_by_staff_id=actor_staff_id,
            actor_name_snapshot=actor_name[:160],
            created_at=now,
        )
        session.add(receipt)
        await session.flush()
        for item in order_items:
            qty = _quantity(item.qty, item.unit or "dona")
            price = int(
                (Decimal(item.line_total) / qty).quantize(
                    Decimal("1"), rounding=ROUND_HALF_EVEN
                )
            ) if item.line_total else _price(item.price_text)
            line = CashReceiptLine(
                receipt_id=receipt.id,
                business_account_id=order.provider_account_id,
                catalog_item_id=item.catalog_item_id,
                inventory_item_id=None,
                legacy_source_key=None,
                item_name=item.item_name,
                qty=qty,
                unit=item.unit or "dona",
                unit_price=price,
                total=item.line_total,
                cost_total=0,
                created_at=now,
            )
            session.add(line)
            await session.flush()
            if item.catalog_item_id is not None:
                inventory_id, total_cost = await self._inventory.consume_cash_line(
                    session,
                    business_account_id=order.provider_account_id,
                    catalog_item_id=item.catalog_item_id,
                    cash_sale_line_id=line.id,
                    qty=qty,
                    actor_staff_id=actor_staff_id,
                    note=f"Buyurtma #{order.id}",
                    now=now,
                )
                line.inventory_item_id = inventory_id
                line.cost_total = total_cost
        await session.flush()
        return receipt

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
        return datetime.combine(value, time(hour=12), tzinfo=UZBEKISTAN_TZ).astimezone(UTC)

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
            can_delete=(
                receipt.source in {"manual", "debt_payment"}
                and receipt.pay_type != "qarz"
            ),
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
