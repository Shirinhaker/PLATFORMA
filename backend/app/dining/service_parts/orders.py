"""Ichki zakazlar: ochish, ro'yxat, taom qo'shish."""

from __future__ import annotations

from app.core.errors import ApiError
from app.dining.model import DiningOrder
from app.dining.schemas import (
    DiningItemsAdd,
    DiningOrderCreate,
    DiningOrderRead,
)
from app.dining.service_parts.base import DiningServiceBase


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
