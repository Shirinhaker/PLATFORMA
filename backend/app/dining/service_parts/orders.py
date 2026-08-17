"""Ichki zakazlar: ochish, ro'yxat, taom qo'shish."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cash_register.model import CashReceipt
from app.core.errors import ApiError
from app.dining.model import DiningOrder, DiningOrderItem
from app.dining.schemas import (
    DiningItemInput,
    DiningItemsAdd,
    DiningOrderCreate,
    DiningOrderRead,
)
from app.dining.service_parts.base import DiningServiceBase
from app.dining.service_parts.helpers import _line_total, _price_of, _quantity


class OrdersMixin(DiningServiceBase):
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
