"""Stollar va xonalar: ro'yxat, tahrirlash, bo'shatish, bron."""

from __future__ import annotations

from app.core.errors import ApiError
from app.dining.model import DiningOrder, DiningPlace
from app.dining.schemas import (
    DiningBookingCreate,
    DiningOrderRead,
    DiningPlaceMove,
    DiningPlaceRead,
    DiningPlaceWrite,
)
from app.dining.service_parts.base import DiningServiceBase


class PlacesMixin(DiningServiceBase):
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
            order_id = next((row.id for row in active if row.kind == "order"), None)
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
