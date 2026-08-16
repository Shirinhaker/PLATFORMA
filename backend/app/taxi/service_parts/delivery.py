"""Yetkazib berish: buyurtma zanjiri bilan bog'lanish."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.orders.model import Order
from app.profiles.model import BusinessProfile
from app.taxi.model import (
    TaxiDriver,
    TaxiRide,
)
from app.taxi.service_parts.base import TaxiServiceBase


class DeliveryMixin(TaxiServiceBase):
    async def after_order_handoff(self, session: AsyncSession, order_id: int) -> None:
        ride = await session.scalar(
            select(TaxiRide)
            .where(
                TaxiRide.source_order_id == order_id,
                TaxiRide.kind == "dostavka",
            )
            .with_for_update()
        )
        if ride is None or ride.status != "pickup_requested":
            raise ApiError(
                409,
                "order_delivery_not_picked_up",
                "Dostavkachi 'Dostavkani oldim' tugmasini hali bosmagan.",
            )
        ride.status = "in_delivery"
        ride.updated_at = self._now()

    async def after_order_ready(self, session: AsyncSession, order: Order) -> None:
        if (
            order.order_type != "delivery"
            or order.provider_kind != "business"
            or order.delivery_lat is None
            or order.delivery_lng is None
        ):
            return
        existing = await session.scalar(
            select(TaxiRide.id).where(TaxiRide.source_order_id == order.id).limit(1)
        )
        if existing is not None:
            return
        business = await session.get(BusinessProfile, order.provider_account_id)
        if business is None:
            return
        distance = None
        if business.latitude is not None and business.longitude is not None:
            distance = self._haversine_km(
                business.latitude,
                business.longitude,
                order.delivery_lat,
                order.delivery_lng,
            )
        from_addr = business.name or "Do'kon"
        if business.address:
            from_addr += f", {business.address}"
        now = self._now()
        session.add(
            TaxiRide(
                legacy_source_id=None,
                customer_account_id=order.provider_account_id,
                driver_id=None,
                source_order_id=order.id,
                kind="dostavka",
                from_addr=from_addr,
                to_addr=order.address or "Mijoz manzili (xaritada)",
                from_lat=business.latitude,
                from_lng=business.longitude,
                to_lat=order.delivery_lat,
                to_lng=order.delivery_lng,
                dist_km=distance,
                dur_min=0,
                meter_km=None,
                ozim=False,
                cargo="",
                car_type="",
                note=f"Do'kon buyurtmasi #{order.id}"
                + (f" — {order.title}" if order.title else ""),
                status="pending",
                created_at=now,
                accepted_at=None,
                updated_at=now,
            )
        )
        await session.flush()

    async def after_order_received(self, session: AsyncSession, order_id: int) -> None:
        ride = await session.scalar(
            select(TaxiRide)
            .where(
                TaxiRide.source_order_id == order_id,
                TaxiRide.kind == "dostavka",
            )
            .with_for_update()
        )
        if ride is None or ride.status != "delivered_waiting_customer":
            raise ApiError(
                409,
                "order_delivery_not_handed",
                "Dostavkachi topshirishni hali tasdiqlamagan.",
            )
        ride.status = "completed"
        ride.updated_at = self._now()
        if ride.driver_id is not None:
            driver = await session.scalar(
                select(TaxiDriver)
                .where(TaxiDriver.id == ride.driver_id)
                .with_for_update()
            )
            if driver is not None:
                driver.available = True
                driver.updated_at = ride.updated_at
