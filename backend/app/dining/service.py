"""Ovqatlanish zanjiri: ofitsiant → oshpaz → kassa → ombor.

Oqim v1656 (`api.py:3503-3860`) bilan bir xil:

    ofitsiant stolga zakaz ochadi
    → oshpaz "tayyor" deb belgilaydi
    → kassir to'lovni tasdiqlaydi (ombor va kassa shu payt yoziladi)
    → kassir hisobni yakunlaydi va stol bo'shaydi

Migratsiyagacha zanjirning oxirgi uchtasi umuman yo'q edi: `kitchen_status`
hech qachon `done`, `payment_status` hech qachon `confirmed` bo'lmagani
uchun stol abadiy band qolardi.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
import re

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cash_register.model import CashReceipt, CashReceiptLine
from app.cash_register.repository import CashRegisterRepository
from app.core.errors import ApiError
from app.debt_ledger.service import DebtLedgerService
from app.dining.model import DiningOrder, DiningOrderItem, DiningPlace
from app.dining.repository import DiningRepository
from app.dining.schemas import (
    DiningBookingCreate,
    DiningCancel,
    DiningCashierItemsUpdate,
    DiningItemInput,
    DiningItemsAdd,
    DiningKitchenUpdate,
    DiningOrderCreate,
    DiningOrderItemRead,
    DiningOrderRead,
    DiningPaymentCreate,
    DiningPaymentResult,
    DiningPlaceMove,
    DiningPlaceRead,
    DiningPlaceWrite,
    DiningProblemOpen,
)
from app.inventory.service import InventoryService
from app.notifications.model import Notification
from app.notifications.repository import NotificationRepository
from app.staff.model import StaffMember


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]

QUANTITY_STEP = Decimal("0.001")
# v1656 `_dining_prepare_items`: butun sonli birliklar yaxlitlanadi.
FRACTIONAL_UNITS = frozenset({"kg", "l", "litr", "gr", "gramm", "m", "m2", "m3"})


def _unix(value: datetime | None) -> int:
    return int(value.timestamp()) if value is not None else 0


def _price_of(value: str) -> int:
    digits = re.sub(r"[^0-9]", "", value or "")
    return int(digits[:12]) if digits else 0


def _quantity(value: Decimal, unit: str) -> Decimal:
    if (unit or "dona") not in FRACTIONAL_UNITS:
        rounded = value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        value = max(Decimal("1"), rounded)
    return value.quantize(QUANTITY_STEP, rounding=ROUND_HALF_EVEN)


def _line_total(price: int, qty: Decimal) -> int:
    return int((Decimal(price) * qty).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


class DiningService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        inventory: InventoryService,
        debt_ledger: DebtLedgerService,
        cash_repository: CashRegisterRepository | None = None,
        repository: DiningRepository | None = None,
        notification_repository: NotificationRepository | None = None,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._inventory = inventory
        self._debt_ledger = debt_ledger
        self._cash = cash_repository or CashRegisterRepository()
        self._repository = repository or DiningRepository()
        self._notifications = notification_repository or NotificationRepository()
        self._now = now_provider

    # ---------------------------------------------------------------- ruxsat

    @staticmethod
    def _require(permissions: tuple[str, ...] | None, *allowed: str) -> None:
        """Rahbar (`permissions is None`) hamma narsani qila oladi."""
        if permissions is None:
            return
        if not any(name in permissions for name in allowed):
            raise ApiError(
                403,
                "staff_permission_required",
                "Bu bo‘limga vakolatingiz yo‘q.",
            )

    # ---------------------------------------------------------------- stollar

    async def list_places(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
    ) -> list[DiningPlaceRead]:
        self._require(permissions, "dining_places", "dining_internal", "kassa")
        async with self._session_factory() as session:
            places = await self._repository.places(
                session, business_account_id=business_account_id
            )
            orders = await self._repository.orders(
                session,
                business_account_id=business_account_id,
                active_only=True,
            )
        # Stol band bo'lsa, ustidagi faol zakaz ko'rsatiladi.
        active: dict[int, int] = {}
        for order in orders:
            if order.kind == "order":
                active.setdefault(order.place_id, order.id)
        return [self._place_read(place, active.get(place.id)) for place in places]

    async def create_place(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        body: DiningPlaceWrite,
    ) -> DiningPlaceRead:
        self._require(permissions, "dining_places")
        now = self._now()
        async with self._session_factory() as session:
            place = DiningPlace(
                business_account_id=business_account_id,
                legacy_source_id=None,
                kind=body.kind,
                name=body.name.strip(),
                seats=body.seats,
                x=body.x,
                y=body.y,
                locked=body.locked,
                created_at=now,
                updated_at=now,
            )
            session.add(place)
            await session.flush()
            result = self._place_read(place, None)
            await session.commit()
        return result

    async def update_place(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        place_id: int,
        body: DiningPlaceWrite | DiningPlaceMove,
    ) -> DiningPlaceRead:
        self._require(permissions, "dining_places")
        async with self._session_factory() as session:
            place = await self._require_place(
                session,
                business_account_id=business_account_id,
                place_id=place_id,
            )
            if isinstance(body, DiningPlaceWrite):
                place.kind = body.kind
                place.name = body.name.strip()
                place.seats = body.seats
                place.locked = body.locked
            elif body.locked is not None:
                place.locked = body.locked
            place.x = body.x
            place.y = body.y
            place.updated_at = self._now()
            active = await self._repository.active_orders_for_place(
                session,
                business_account_id=business_account_id,
                place_id=place_id,
            )
            order_id = next(
                (row.id for row in active if row.kind == "order"), None
            )
            result = self._place_read(place, order_id)
            await session.commit()
        return result

    async def delete_place(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        place_id: int,
    ) -> None:
        self._require(permissions, "dining_places")
        async with self._session_factory() as session:
            place = await self._require_place(
                session,
                business_account_id=business_account_id,
                place_id=place_id,
            )
            active = await self._repository.active_orders_for_place(
                session,
                business_account_id=business_account_id,
                place_id=place_id,
            )
            if any(row.kind == "order" for row in active):
                raise ApiError(
                    409,
                    "dining_place_has_unfinished_order",
                    "Ochiq hisobi bor stolni o‘chirib bo‘lmaydi.",
                )
            await session.delete(place)
            await session.commit()

    async def clear_place(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        place_id: int,
    ) -> None:
        """Stolni bo'shatadi — v1656 `dining_place_clear`."""
        self._require(permissions, "dining_places", "kassa")
        now = self._now()
        async with self._session_factory() as session:
            await self._require_place(
                session,
                business_account_id=business_account_id,
                place_id=place_id,
            )
            orders = await self._repository.active_orders_for_place(
                session,
                business_account_id=business_account_id,
                place_id=place_id,
                lock=True,
            )
            unfinished = any(
                order.kind == "order"
                and (
                    order.payment_status != "confirmed"
                    or order.kitchen_status != "done"
                )
                for order in orders
            )
            if unfinished:
                raise ApiError(
                    409,
                    "dining_place_has_unfinished_order",
                    "Stolni bo‘shatish uchun taom tayyor va to‘lov "
                    "tasdiqlangan bo‘lishi kerak.",
                )
            for order in orders:
                order.status = "done"
                order.updated_at = now
            await session.commit()

    # ------------------------------------------------------------- zakazlar

    async def book(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        place_id: int,
        body: DiningBookingCreate,
    ) -> DiningOrderRead:
        self._require(permissions, "dining_places", "dining_internal")
        now = self._now()
        async with self._session_factory() as session:
            place = await self._require_place(
                session,
                business_account_id=business_account_id,
                place_id=place_id,
            )
            order = DiningOrder(
                business_account_id=business_account_id,
                place_id=place.id,
                kind="booking",
                customer_name=body.customer_name.strip(),
                phone=body.phone.strip(),
                booking_date=body.booking_date.strip(),
                booking_time=body.booking_time.strip(),
                guests=body.guests,
                note=body.note.strip(),
                total=0,
                created_at=now,
                updated_at=now,
            )
            session.add(order)
            await session.flush()
            result = self._order_read(order, place.name, place.kind, [])
            await session.commit()
        return result

    async def create_order(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        place_id: int,
        actor_staff_id: int | None,
        body: DiningOrderCreate,
    ) -> DiningOrderRead:
        self._require(permissions, "dining_internal")
        now = self._now()
        async with self._session_factory() as session:
            place = await self._require_place(
                session,
                business_account_id=business_account_id,
                place_id=place_id,
            )
            prepared = await self._prepare_items(
                session,
                business_account_id=business_account_id,
                incoming=body.items,
                empty_message="Zakaz uchun mahsulot tanlanmadi.",
            )
            order = DiningOrder(
                business_account_id=business_account_id,
                place_id=place.id,
                kind="order",
                customer_name=body.customer_name.strip(),
                note=body.note.strip(),
                total=sum(line["total"] for line in prepared),
                waiter_staff_id=actor_staff_id,
                waiter_name=await self._actor_name(session, actor_staff_id),
                kitchen_status="preparing",
                payment_status="open",
                status="active",
                created_at=now,
                updated_at=now,
            )
            session.add(order)
            await session.flush()
            items = self._add_lines(
                session,
                order=order,
                business_account_id=business_account_id,
                prepared=prepared,
                now=now,
            )
            await session.flush()
            await self._notify_new_order(
                session,
                business_account_id=business_account_id,
                order=order,
                place_name=place.name,
                amount=order.total,
                now=now,
            )
            result = self._order_read(order, place.name, place.kind, items)
            await session.commit()
        return result

    async def list_orders(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
    ) -> list[DiningOrderRead]:
        self._require(
            permissions, "dining_internal", "kitchen", "kassa", "dining_places"
        )
        async with self._session_factory() as session:
            orders = await self._repository.orders(
                session, business_account_id=business_account_id
            )
            places = {
                place.id: (place.name, place.kind)
                for place in await self._repository.places(
                    session, business_account_id=business_account_id
                )
            }
            grouped = await self._repository.items_for_orders(
                session, order_ids=[order.id for order in orders]
            )
            receipts = await self._receipt_numbers(session, orders)
        return [
            self._order_read(
                order,
                *places.get(order.place_id, ("Stol", "table")),
                grouped.get(order.id, []),
                receipt_no=receipts.get(order.id),
            )
            for order in orders
        ]

    async def add_items(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        order_id: int,
        body: DiningItemsAdd,
    ) -> DiningOrderRead:
        """Ofitsiant mavjud qatorni o'zgartirmaydi, faqat yangi qo'shadi."""
        self._require(permissions, "dining_internal", "kassa")
        now = self._now()
        async with self._session_factory() as session:
            order = await self._require_order(
                session,
                business_account_id=business_account_id,
                order_id=order_id,
                lock=True,
            )
            if order.status != "active" or order.payment_status == "confirmed":
                raise ApiError(
                    400,
                    "completed_dining_order",
                    "Yakunlangan hisobga taom qo‘shib bo‘lmaydi.",
                )
            prepared = await self._prepare_items(
                session,
                business_account_id=business_account_id,
                incoming=body.items,
                empty_message="Qo‘shiladigan taom tanlanmadi.",
            )
            added = sum(line["total"] for line in prepared)
            self._add_lines(
                session,
                order=order,
                business_account_id=business_account_id,
                prepared=prepared,
                now=now,
            )
            await session.flush()
            order.total += added
            # Tayyor deb belgilangan hisobga yangi taom kelsa,
            # oshxona jarayoni qayta ochiladi.
            order.kitchen_status = "preparing"
            order.updated_at = now
            place_name, place_kind = await self._place_of(session, order)
            await self._notify_added_items(
                session,
                business_account_id=business_account_id,
                order=order,
                place_name=place_name,
                amount=added,
                now=now,
            )
            items = await self._repository.items(session, order_id=order.id)
            result = self._order_read(order, place_name, place_kind, items)
            await session.commit()
        return result

    # -------------------------------------------------------------- oshxona

    async def set_kitchen_status(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        order_id: int,
        body: DiningKitchenUpdate,
    ) -> DiningOrderRead:
        """Oshpaz taomni tayyorlanmoqda yoki tayyor deb belgilaydi."""
        self._require(permissions, "kitchen")
        now = self._now()
        async with self._session_factory() as session:
            order = await self._require_order(
                session,
                business_account_id=business_account_id,
                order_id=order_id,
                lock=True,
            )
            if order.status != "active":
                raise ApiError(
                    409,
                    "dining_order_closed",
                    "Yakunlangan buyurtma o‘zgartirilmaydi.",
                )
            if order.problem_open:
                raise ApiError(
                    409,
                    "dining_order_problem_open",
                    "Muammoli zakazni avval kassada hal qiling.",
                )
            order.kitchen_status = body.status
            order.updated_at = now
            place_name, place_kind = await self._place_of(session, order)
            if body.status == "done":
                await self._notify(
                    session,
                    business_account_id=business_account_id,
                    event_key=f"dining:{order.id}:ready:waiter",
                    title="Taom tayyor bo‘ldi",
                    body_text=(
                        f"{order.waiter_name or 'Ofitsiant'} uchun zakazni "
                        "olib ketishingiz mumkin."
                    ),
                    action_type="dining_waiter",
                    order_id=order.id,
                    target_perm="dining_internal",
                    now=now,
                )
                await self._resolve(
                    session,
                    business_account_id=business_account_id,
                    order_id=order.id,
                    action_type="dining_kitchen",
                    now=now,
                )
            items = await self._repository.items(session, order_id=order.id)
            result = self._order_read(order, place_name, place_kind, items)
            await session.commit()
        return result

    # ----------------------------------------------------------------- kassa

    async def confirm_payment(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        order_id: int,
        actor_staff_id: int | None,
        body: DiningPaymentCreate,
    ) -> DiningPaymentResult:
        """To'lovni tasdiqlaydi: Kassa cheki, Ombor sarfi va kerak bo'lsa qarz.

        Uchalasi bitta tranzaksiyada yoziladi — chek yozilib, ombor
        yozilmay qolishi mumkin emas.
        """
        self._require(permissions, "payment_confirm", "kassa")
        now = self._now()
        async with self._session_factory() as session:
            order = await self._require_order(
                session,
                business_account_id=business_account_id,
                order_id=order_id,
                lock=True,
            )
            if order.payment_status == "confirmed":
                receipt_no = await self._receipt_no_for(session, order)
                return DiningPaymentResult(
                    pay_type=order.pay_type,
                    receipt_no=receipt_no,
                    already_confirmed=True,
                )
            if order.problem_open:
                raise ApiError(
                    409,
                    "dining_order_problem_open",
                    "Muammoli zakaz to‘lovi tasdiqlanmaydi. "
                    "Avval muammoni hal qiling.",
                )
            if order.status != "active":
                raise ApiError(
                    409,
                    "dining_order_closed",
                    "Bu ichki buyurtma allaqachon yopilgan.",
                )
            items = await self._repository.items(
                session, order_id=order.id, lock=True
            )
            if not items:
                raise ApiError(
                    400,
                    "dining_order_empty",
                    "Bo‘sh hisob to‘lovi tasdiqlanmaydi.",
                )
            # Ombor qatorlarini bir tartibda qulflash — deadlockni oldini oladi.
            await self._inventory.lock_cash_catalog_items(
                session,
                business_account_id=business_account_id,
                catalog_item_ids=[
                    item.catalog_item_id
                    for item in items
                    if item.catalog_item_id is not None
                ],
            )
            receipt_no = await self._cash.next_receipt_no(
                session,
                business_account_id=business_account_id,
                now=now,
            )
            receipt = CashReceipt(
                business_account_id=business_account_id,
                receipt_no=receipt_no,
                source="dining",
                order_id=None,
                legacy_order_source_id=None,
                legacy_group_key=None,
                pay_type=body.pay_type,
                debtor_id=None,
                debtor_name_snapshot="",
                legacy_debtor_source_id=None,
                note=f"Ichki buyurtma #{order.id}",
                created_by_staff_id=actor_staff_id,
                actor_name_snapshot=await self._actor_name(
                    session, actor_staff_id
                ),
                waiter_staff_id=order.waiter_staff_id,
                waiter_name_snapshot=order.waiter_name,
                created_at=now,
            )
            session.add(receipt)
            await session.flush()

            if body.pay_type == "qarz":
                if body.debtor_id is None:
                    raise ApiError(
                        400,
                        "debt_debtor_required",
                        "Qarz uchun qarzdorni tanlang.",
                    )
                debtor = await self._debt_ledger.require_debtor_in_session(
                    session,
                    business_account_id=business_account_id,
                    debtor_id=body.debtor_id,
                    lock=True,
                )
                await self._debt_ledger.create_transaction_in_session(
                    session,
                    business_account_id=business_account_id,
                    debtor_id=debtor.id,
                    transaction_type="debt",
                    amount=order.total,
                    transaction_date=now.date(),
                    note=f"Ichki buyurtma #{order.id}",
                    actor_staff_id=actor_staff_id,
                    cash_receipt_id=receipt.id,
                    debtor=debtor,
                )
                receipt.debtor_id = debtor.id
                receipt.debtor_name_snapshot = debtor.name
                receipt.legacy_debtor_source_id = debtor.legacy_source_id
                order.debtor_id = debtor.id

            for item in items:
                line = CashReceiptLine(
                    receipt_id=receipt.id,
                    business_account_id=business_account_id,
                    catalog_item_id=item.catalog_item_id,
                    inventory_item_id=None,
                    legacy_source_key=None,
                    item_name=item.name,
                    qty=item.qty,
                    unit=item.unit,
                    unit_price=item.price,
                    total=item.total,
                    cost_total=0,
                    created_at=now,
                )
                session.add(line)
                await session.flush()
                if item.catalog_item_id is None:
                    continue
                inventory_id, cost = await self._inventory.consume_cash_line(
                    session,
                    business_account_id=business_account_id,
                    catalog_item_id=item.catalog_item_id,
                    cash_sale_line_id=line.id,
                    qty=item.qty,
                    actor_staff_id=actor_staff_id,
                    note=f"Ichki buyurtma #{order.id}",
                    now=now,
                )
                line.inventory_item_id = inventory_id
                line.cost_total = cost

            # Ombor sarfi va chek qatorlari yozilib bo'lgach holat
            # o'zgaradi — bildirishnoma yuborilishidan oldin.
            await session.flush()
            order.payment_status = "confirmed"
            order.pay_type = body.pay_type
            order.cash_receipt_id = receipt.id
            order.updated_at = now
            await self._notify(
                session,
                business_account_id=business_account_id,
                event_key=f"dining:{order.id}:paid:kitchen",
                title="Ichki zakaz to‘lovi tasdiqlandi",
                body_text=(
                    f"Zakaz #{order.id} to‘lovi kassir tomonidan tasdiqlandi."
                ),
                action_type="dining_kitchen",
                order_id=order.id,
                target_perm="kitchen",
                now=now,
                requires_action=False,
            )
            await self._resolve(
                session,
                business_account_id=business_account_id,
                order_id=order.id,
                action_type="dining_cash",
                now=now,
            )
            await session.commit()
        return DiningPaymentResult(pay_type=body.pay_type, receipt_no=receipt_no)

    async def update_cashier_items(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        order_id: int,
        body: DiningCashierItemsUpdate,
    ) -> DiningOrderRead:
        """Kassir hisob yopilguncha qator miqdorini o'zgartiradi."""
        self._require(permissions, "kassa")
        now = self._now()
        async with self._session_factory() as session:
            order = await self._require_order(
                session,
                business_account_id=business_account_id,
                order_id=order_id,
                lock=True,
            )
            if order.status != "active" or order.payment_status == "confirmed":
                raise ApiError(
                    400,
                    "dining_order_closed",
                    "Yopilgan hisobni tahrirlab bo‘lmaydi.",
                )
            rows = {
                item.id: item
                for item in await self._repository.items(
                    session, order_id=order.id, lock=True
                )
            }
            for change in body.items:
                item = rows.get(change.line_id)
                if item is None:
                    continue
                if change.qty <= 0:
                    await session.delete(item)
                    rows.pop(change.line_id)
                    continue
                item.qty = _quantity(change.qty, item.unit)
                item.total = _line_total(item.price, item.qty)
            total = sum(item.total for item in rows.values())
            if total <= 0:
                # Rollback'dan keyin ORM obyektlarini o'qish mumkin emas,
                # shuning uchun xabar oldindan tayyor.
                await session.rollback()
                raise ApiError(
                    400,
                    "dining_order_empty",
                    "Hisobda kamida bitta taom qolishi kerak.",
                )
            order.total = total
            order.updated_at = now
            place_name, place_kind = await self._place_of(session, order)
            items = await self._repository.items(session, order_id=order.id)
            result = self._order_read(order, place_name, place_kind, items)
            await session.commit()
        return result

    async def finalize(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        order_id: int,
    ) -> DiningOrderRead:
        """Hisobni yopadi va stolni bo'shatadi."""
        self._require(permissions, "kassa", "payment_confirm")
        now = self._now()
        async with self._session_factory() as session:
            order = await self._require_order(
                session,
                business_account_id=business_account_id,
                order_id=order_id,
                lock=True,
            )
            place_name, place_kind = await self._place_of(session, order)
            if order.status == "done":
                items = await self._repository.items(session, order_id=order.id)
                return self._order_read(order, place_name, place_kind, items)
            if order.problem_open:
                raise ApiError(
                    409,
                    "dining_order_problem_open",
                    "Muammoli zakazni yakunlab bo‘lmaydi. "
                    "Avval muammoni hal qiling.",
                )
            if order.payment_status != "confirmed":
                raise ApiError(
                    409,
                    "dining_payment_required",
                    "Avval to‘lovni tasdiqlang.",
                )
            if order.kitchen_status != "done":
                raise ApiError(
                    409,
                    "dining_kitchen_pending",
                    "Oshpaz buyurtmani hali tayyor qilmagan.",
                )
            order.status = "done"
            order.updated_at = now
            items = await self._repository.items(session, order_id=order.id)
            result = self._order_read(order, place_name, place_kind, items)
            await session.commit()
        return result

    async def cancel(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        order_id: int,
        body: DiningCancel,
    ) -> DiningOrderRead:
        """To'lovi tasdiqlanmagan zakazni bekor qiladi."""
        self._require(permissions, "kassa")
        now = self._now()
        async with self._session_factory() as session:
            order = await self._require_order(
                session,
                business_account_id=business_account_id,
                order_id=order_id,
                lock=True,
            )
            if order.payment_status == "confirmed":
                raise ApiError(
                    409,
                    "dining_order_paid",
                    "To‘lovi tasdiqlangan ichki buyurtmani bekor qilib "
                    "bo‘lmaydi.",
                )
            if order.status != "active":
                raise ApiError(
                    409,
                    "dining_order_closed",
                    "Bu ichki buyurtma allaqachon yopilgan.",
                )
            order.status = "cancelled"
            order.problem_open = False
            order.problem_reason = "Bekor qilindi"
            order.problem_note = body.reason.strip()
            order.updated_at = now
            place_name, place_kind = await self._place_of(session, order)
            await self._resolve(
                session,
                business_account_id=business_account_id,
                order_id=order.id,
                action_type=None,
                now=now,
            )
            await self._notify(
                session,
                business_account_id=business_account_id,
                event_key=f"dining:{order.id}:cancelled:kitchen",
                title="Ichki zakaz bekor qilindi",
                body_text=f"{place_name} · {order.problem_note}",
                action_type="dining_cancelled",
                order_id=order.id,
                target_perm="kitchen",
                now=now,
                requires_action=False,
            )
            items = await self._repository.items(session, order_id=order.id)
            result = self._order_read(order, place_name, place_kind, items)
            await session.commit()
        return result

    async def open_problem(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        order_id: int,
        body: DiningProblemOpen,
    ) -> DiningOrderRead:
        self._require(permissions, "kassa", "payment_problems")
        now = self._now()
        async with self._session_factory() as session:
            order = await self._require_order(
                session,
                business_account_id=business_account_id,
                order_id=order_id,
                lock=True,
            )
            if order.status != "active" or order.payment_status == "confirmed":
                raise ApiError(
                    409,
                    "dining_order_closed",
                    "Yopilgan yoki to‘lovi tasdiqlangan hisob muammoliga "
                    "o‘tkazilmaydi.",
                )
            reason = (body.reason or "Boshqa").strip()[:80]
            order.problem_open = True
            order.problem_reason = reason
            order.problem_note = body.note.strip()
            order.problem_opened_at = now
            order.updated_at = now
            place_name, place_kind = await self._place_of(session, order)
            suffix = f" · {order.problem_note}" if order.problem_note else ""
            await self._notify(
                session,
                business_account_id=business_account_id,
                event_key=f"dining:{order.id}:problem",
                title="Ichki hisobda muammo",
                body_text=f"{reason}{suffix}",
                action_type="dining_problem",
                order_id=order.id,
                target_perm="kassa",
                now=now,
            )
            items = await self._repository.items(session, order_id=order.id)
            result = self._order_read(order, place_name, place_kind, items)
            await session.commit()
        return result

    async def resolve_problem(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        order_id: int,
    ) -> DiningOrderRead:
        self._require(permissions, "kassa", "payment_problems")
        now = self._now()
        async with self._session_factory() as session:
            order = await self._require_order(
                session,
                business_account_id=business_account_id,
                order_id=order_id,
                lock=True,
            )
            place_name, place_kind = await self._place_of(session, order)
            if not order.problem_open:
                items = await self._repository.items(session, order_id=order.id)
                return self._order_read(order, place_name, place_kind, items)
            order.problem_open = False
            order.updated_at = now
            await self._resolve(
                session,
                business_account_id=business_account_id,
                order_id=order.id,
                action_type="dining_problem",
                now=now,
            )
            items = await self._repository.items(session, order_id=order.id)
            result = self._order_read(order, place_name, place_kind, items)
            await session.commit()
        return result

    # -------------------------------------------------------------- yordamchi

    async def _require_place(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        place_id: int,
    ) -> DiningPlace:
        place = await self._repository.place(
            session,
            business_account_id=business_account_id,
            place_id=place_id,
        )
        if place is None:
            raise ApiError(
                404, "dining_place_not_found", "Stol yoki xona topilmadi."
            )
        return place

    async def _require_order(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        order_id: int,
        lock: bool = False,
    ) -> DiningOrder:
        order = await self._repository.order(
            session,
            business_account_id=business_account_id,
            order_id=order_id,
            lock=lock,
        )
        if order is None:
            raise ApiError(
                404, "dining_order_not_found", "Ichki buyurtma topilmadi."
            )
        return order

    async def _actor_name(
        self, session: AsyncSession, staff_id: int | None
    ) -> str:
        """Xodim ismini bazadan oladi; rahbar uchun v1656dagi 'Rahbar'."""
        if staff_id is None:
            return "Rahbar"
        name = await session.scalar(
            select(StaffMember.name).where(StaffMember.id == staff_id)
        )
        return (name or "Xodim")[:80]

    async def _place_of(
        self, session: AsyncSession, order: DiningOrder
    ) -> tuple[str, str]:
        """Stol nomi va turi — oshpaz kartasi ikkalasini ko'rsatadi."""
        place = await session.get(DiningPlace, order.place_id)
        if place is None:
            return "Stol", "table"
        return place.name, place.kind

    async def _prepare_items(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        incoming: list[DiningItemInput],
        empty_message: str,
    ) -> list[dict[str, object]]:
        """Narxni serverdagi katalogdan oladi — mijoz yuborgani ishonchsiz."""
        wanted: dict[int, Decimal] = {}
        for entry in incoming:
            wanted[entry.item_id] = wanted.get(entry.item_id, Decimal(0)) + entry.qty
        if not wanted:
            raise ApiError(400, "dining_items_required", empty_message)
        rows = await self._repository.menu_items(
            session,
            business_account_id=business_account_id,
            catalog_item_ids=list(wanted),
        )
        prepared: list[dict[str, object]] = []
        for row in rows:
            unit = row.unit or "dona"
            qty = _quantity(wanted[row.id], unit)
            price = _price_of(row.price_text)
            prepared.append({
                "catalog_item_id": row.id,
                "name": row.name,
                "qty": qty,
                "unit": unit,
                "price": price,
                "total": _line_total(price, qty),
            })
        if not prepared:
            raise ApiError(
                400, "dining_items_missing", "Tanlangan taomlar topilmadi."
            )
        return prepared

    def _add_lines(
        self,
        session: AsyncSession,
        *,
        order: DiningOrder,
        business_account_id: int,
        prepared: list[dict[str, object]],
        now: datetime,
    ) -> list[DiningOrderItem]:
        items = [
            DiningOrderItem(
                order_id=order.id,
                business_account_id=business_account_id,
                catalog_item_id=line["catalog_item_id"],
                name=line["name"],
                qty=line["qty"],
                unit=line["unit"],
                price=line["price"],
                total=line["total"],
                created_at=now,
            )
            for line in prepared
        ]
        session.add_all(items)
        return items

    async def _receipt_no_for(
        self, session: AsyncSession, order: DiningOrder
    ) -> int | None:
        if order.cash_receipt_id is None:
            return None
        return await session.scalar(
            select(CashReceipt.receipt_no).where(
                CashReceipt.id == order.cash_receipt_id
            )
        )

    async def _receipt_numbers(
        self, session: AsyncSession, orders: list[DiningOrder]
    ) -> dict[int, int | None]:
        wanted = {
            order.cash_receipt_id: order.id
            for order in orders
            if order.cash_receipt_id is not None
        }
        if not wanted:
            return {}
        rows = (await session.execute(
            select(CashReceipt.id, CashReceipt.receipt_no).where(
                CashReceipt.id.in_(wanted)
            )
        )).all()
        return {wanted[row.id]: row.receipt_no for row in rows}

    # ------------------------------------------------------- bildirishnomalar

    async def _notify(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        event_key: str,
        title: str,
        body_text: str,
        action_type: str,
        order_id: int,
        target_perm: str,
        now: datetime,
        requires_action: bool = True,
    ) -> None:
        if not self._notifications.supported(session):
            return
        await self._notifications.append(
            session,
            account_id=business_account_id,
            account_type="business",
            row={
                "event_key": event_key,
                "title": title,
                "body": body_text,
                "action_type": action_type,
                "requires_action": requires_action,
                "created_at": int(now.timestamp()),
                # `notifications` jadvalida dining ustuni yo'q —
                # bu ikkisi `payload` ichiga tushadi.
                "dining_order_id": order_id,
                "target_perm": target_perm,
            },
        )

    async def _resolve(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        order_id: int,
        action_type: str | None,
        now: datetime,
    ) -> None:
        """Zakaz bo'yicha ochiq chaqiriqlarni yopadi."""
        statement = (
            update(Notification)
            .where(
                Notification.account_id == business_account_id,
                Notification.account_type == "business",
                Notification.requires_action.is_(True),
                Notification.is_read.is_(False),
                Notification.payload["dining_order_id"].as_integer()
                == order_id,
            )
            .values(is_read=True, read_at=int(now.timestamp()))
        )
        if action_type is not None:
            statement = statement.where(Notification.action_type == action_type)
        await session.execute(statement)

    async def _notify_new_order(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        order: DiningOrder,
        place_name: str,
        amount: int,
        now: datetime,
    ) -> None:
        await self._notify(
            session,
            business_account_id=business_account_id,
            event_key=f"dining:{order.id}:kitchen",
            title="Yangi ichki zakaz",
            body_text=f"{place_name} · {amount} so‘m",
            action_type="dining_kitchen",
            order_id=order.id,
            target_perm="kitchen",
            now=now,
        )
        await self._notify(
            session,
            business_account_id=business_account_id,
            event_key=f"dining:{order.id}:cash",
            title="Yangi ochiq hisob",
            body_text=f"{place_name} · {amount} so‘m",
            action_type="dining_cash",
            order_id=order.id,
            target_perm="kassa",
            now=now,
        )

    async def _notify_added_items(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        order: DiningOrder,
        place_name: str,
        amount: int,
        now: datetime,
    ) -> None:
        stamp = int(now.timestamp())
        await self._notify(
            session,
            business_account_id=business_account_id,
            event_key=f"dining:{order.id}:items:{stamp}:kitchen",
            title="Ichki zakazga yangi taom qo‘shildi",
            body_text=f"{place_name} · +{amount} so‘m",
            action_type="dining_kitchen",
            order_id=order.id,
            target_perm="kitchen",
            now=now,
        )
        await self._notify(
            session,
            business_account_id=business_account_id,
            event_key=f"dining:{order.id}:items:{stamp}:cash",
            title="Ichki zakaz hisobi yangilandi",
            body_text=f"{place_name} · +{amount} so‘m",
            action_type="dining_cash",
            order_id=order.id,
            target_perm="kassa",
            now=now,
        )

    # ------------------------------------------------------------- javoblar

    @staticmethod
    def _place_read(
        place: DiningPlace, active_order_id: int | None
    ) -> DiningPlaceRead:
        return DiningPlaceRead(
            id=place.id,
            kind=place.kind,
            name=place.name,
            seats=place.seats,
            x=place.x,
            y=place.y,
            locked=place.locked,
            active_order_id=active_order_id,
            occupied=active_order_id is not None,
            created_at=_unix(place.created_at),
            updated_at=_unix(place.updated_at),
        )

    @staticmethod
    def _order_read(
        order: DiningOrder,
        place_name: str,
        place_kind: str,
        items: list[DiningOrderItem],
        *,
        receipt_no: int | None = None,
    ) -> DiningOrderRead:
        return DiningOrderRead(
            id=order.id,
            place_id=order.place_id,
            place_name=place_name,
            place_kind=place_kind,
            kind=order.kind,
            customer_name=order.customer_name,
            phone=order.phone,
            booking_date=order.booking_date,
            booking_time=order.booking_time,
            guests=order.guests,
            note=order.note,
            total=order.total,
            waiter_staff_id=order.waiter_staff_id,
            waiter_name=order.waiter_name,
            problem_open=order.problem_open,
            problem_reason=order.problem_reason,
            problem_note=order.problem_note,
            problem_opened_at=_unix(order.problem_opened_at),
            kitchen_status=order.kitchen_status,
            payment_status=order.payment_status,
            pay_type=order.pay_type,
            debtor_id=order.debtor_id,
            receipt_no=receipt_no,
            status=order.status,
            created_at=_unix(order.created_at),
            updated_at=_unix(order.updated_at),
            items=[
                DiningOrderItemRead(
                    id=item.id,
                    item_id=item.catalog_item_id,
                    name=item.name,
                    qty=float(item.qty),
                    unit=item.unit,
                    price=item.price,
                    total=item.total,
                )
                for item in items
            ],
        )
