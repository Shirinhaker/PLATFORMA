"""Umumiy asos: bog'liqliklar, huquq tekshiruvi, bildirishnomalar.

`_prepare_items` va `_receipt_numbers` — zanjirning bir necha
bosqichida kerak, shuning uchun shu yerda.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cash_register.model import CashReceipt
from app.cash_register.repository import CashRegisterRepository
from app.core.errors import ApiError
from app.debt_ledger.service import DebtLedgerService
from app.dining.model import DiningOrder, DiningOrderItem, DiningPlace
from app.dining.repository import DiningRepository
from app.dining.schemas import (
    DiningItemInput,
    DiningOrderItemRead,
    DiningOrderRead,
    DiningPlaceRead,
)
from app.dining.service_parts.helpers import (
    SessionFactory,
    _line_total,
    _price_of,
    _quantity,
    _unix,
)
from app.inventory.service_parts import InventoryService
from app.notifications.model import Notification
from app.notifications.repository import NotificationRepository
from app.staff.model import StaffMember


class DiningServiceBase:
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
            raise ApiError(404, "dining_place_not_found", "Stol yoki xona topilmadi.")
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
            raise ApiError(404, "dining_order_not_found", "Ichki buyurtma topilmadi.")
        return order

    async def _actor_name(self, session: AsyncSession, staff_id: int | None) -> str:
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
            prepared.append(
                {
                    "catalog_item_id": row.id,
                    "name": row.name,
                    "qty": qty,
                    "unit": unit,
                    "price": price,
                    "total": _line_total(price, qty),
                }
            )
        if not prepared:
            raise ApiError(400, "dining_items_missing", "Tanlangan taomlar topilmadi.")
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
        rows = (
            await session.execute(
                select(CashReceipt.id, CashReceipt.receipt_no).where(
                    CashReceipt.id.in_(wanted)
                )
            )
        ).all()
        return {wanted[row.id]: row.receipt_no for row in rows}

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
                Notification.payload["dining_order_id"].as_integer() == order_id,
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

    @staticmethod
    def _place_read(place: DiningPlace, active_order_id: int | None) -> DiningPlaceRead:
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
