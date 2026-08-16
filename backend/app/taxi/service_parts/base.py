"""Umumiy asos: haydovchi/safar yuklash, masofa hisobi, javob shakli."""

from __future__ import annotations

import math
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.notifications.repository import NotificationRepository
from app.orders.model import Order
from app.orders.notifications import append_order_notification
from app.profiles.model import BusinessProfile, UserProfile
from app.taxi.model import (
    DRIVER_ACTIVE_STATUSES,
    TaxiDriver,
    TaxiRide,
)
from app.taxi.schemas import (
    DriverRead,
    RideDriver,
    RidePerson,
    RideRead,
)
from app.taxi.service_parts.helpers import (
    COMMISSION_PER_ORDER,
    NowProvider,
    SessionFactory,
    calculate_price,
)


class TaxiServiceBase:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._now = now_provider or (lambda: datetime.now(UTC))
        self._notifications = NotificationRepository()

    async def _sync_source_order(
        self,
        session: AsyncSession,
        ride: TaxiRide,
        ride_status: str,
    ) -> None:
        if ride.kind != "dostavka" or ride.source_order_id is None:
            return
        order = await session.scalar(
            select(Order).where(Order.id == ride.source_order_id).with_for_update()
        )
        if order is None:
            return
        order_status = {
            "accepted": "courier_assigned",
            "arrived_store": "courier_arrived_store",
            "pickup_requested": "handoff_waiting_seller",
            "arrived_customer": "courier_arrived_customer",
            "delivered_waiting_customer": "delivered_waiting_customer",
        }.get(ride_status)
        if order_status is None:
            return
        order.status = order_status
        order.updated_at = self._now()
        order.customer_seen_at = None
        order.provider_seen_at = None
        order.last_event = "delivery"
        if ride_status == "accepted":
            driver = (
                await session.get(TaxiDriver, ride.driver_id)
                if ride.driver_id
                else None
            )
            profile = (
                await session.get(UserProfile, driver.user_account_id)
                if driver
                else None
            )
            name = profile.name if profile else "Dostavkachi"
            await append_order_notification(
                session,
                self._notifications,
                order,
                side="customer",
                event="courier_assigned",
                title="Dostavkachi buyurtmani qabul qildi",
                body=name,
            )
            await append_order_notification(
                session,
                self._notifications,
                order,
                side="provider",
                event="courier_assigned",
                title="Dostavkachi biriktirildi",
                body=name,
            )
        elif ride_status == "pickup_requested":
            await append_order_notification(
                session,
                self._notifications,
                order,
                side="provider",
                event="courier_pickup_requested",
                title="Dostavkachi buyurtmani olishga tayyor",
                body="Buyurtmani dostavkachiga topshiring.",
                action_type="confirm_handoff",
            )
        elif ride_status == "arrived_customer":
            await append_order_notification(
                session,
                self._notifications,
                order,
                side="customer",
                event="courier_arrived",
                title="Dostavkachi yetib keldi",
                body="Buyurtmani qabul qilishga tayyorlaning.",
            )
        elif ride_status == "delivered_waiting_customer":
            await append_order_notification(
                session,
                self._notifications,
                order,
                side="customer",
                event="delivery_handed",
                title="Buyurtma topshirildi",
                body="Buyurtmani olganingizni tasdiqlang.",
                action_type="confirm_received",
            )

    async def _ride_read(
        self, session: AsyncSession, ride: TaxiRide, *, include_customer: bool = False
    ) -> RideRead:
        driver_payload = None
        if ride.driver_id is not None:
            driver = await session.get(TaxiDriver, ride.driver_id)
            profile = (
                await session.get(UserProfile, driver.user_account_id)
                if driver
                else None
            )
            if driver is not None:
                driver_payload = RideDriver(
                    name=profile.name if profile else "",
                    phone=driver.phone,
                    car_model=driver.car_model,
                    car_color=driver.car_color,
                    car_plate=driver.car_plate,
                )
        customer_payload = None
        if include_customer:
            profile = await session.get(UserProfile, ride.customer_account_id)
            if profile is None:
                profile = await session.get(BusinessProfile, ride.customer_account_id)
            customer_payload = RidePerson(
                name=profile.name if profile else "",
                phone=profile.phone if profile else "",
            )
        return RideRead(
            id=ride.id,
            kind=ride.kind,
            from_addr=ride.from_addr,
            to_addr=ride.to_addr,
            from_lat=ride.from_lat,
            from_lng=ride.from_lng,
            to_lat=ride.to_lat,
            to_lng=ride.to_lng,
            dist_km=ride.dist_km,
            dur_min=ride.dur_min,
            price=calculate_price(ride.kind, ride.dist_km),
            meter_km=ride.meter_km,
            final_price=calculate_price(ride.kind, ride.meter_km),
            ozim=ride.ozim,
            cargo=ride.cargo,
            car_type=ride.car_type,
            note=ride.note,
            status=ride.status,
            source_order_id=ride.source_order_id,
            created_at=ride.created_at,
            accepted_at=ride.accepted_at,
            driver=driver_payload,
            customer=customer_payload,
            customer_name=customer_payload.name if customer_payload else "",
        )

    @staticmethod
    def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        radians = math.pi / 180
        delta_lat = (lat2 - lat1) * radians
        delta_lng = (lng2 - lng1) * radians
        value = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1 * radians)
            * math.cos(lat2 * radians)
            * math.sin(delta_lng / 2) ** 2
        )
        return round(6371 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value)), 1)

    @staticmethod
    def _driver_read(
        driver: TaxiDriver, profile: UserProfile | None, busy: bool
    ) -> DriverRead:
        return DriverRead(
            exists=True,
            id=driver.id,
            name=profile.name if profile else "",
            phone=driver.phone,
            car_model=driver.car_model,
            car_color=driver.car_color,
            car_plate=driver.car_plate,
            service=driver.service,
            available=driver.available and not busy,
            busy=busy,
            rating_sum=driver.rating_sum,
            rating_count=driver.rating_count,
            balance=driver.balance,
            commission=COMMISSION_PER_ORDER,
            status=driver.status,
        )

    async def _driver_for_user(self, session, user_account_id: int, lock: bool = False):
        statement = select(TaxiDriver).where(
            TaxiDriver.user_account_id == user_account_id
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def _require_driver(self, session, user_account_id: int, lock: bool = False):
        driver = await self._driver_for_user(session, user_account_id, lock)
        if driver is None:
            raise ApiError(
                403, "driver_required", "Avval haydovchi sifatida ro'yxatdan o'ting."
            )
        if driver.status != "active":
            raise ApiError(403, "driver_blocked", "Haydovchi profilingiz faol emas.")
        return driver

    @staticmethod
    async def _ride(session, ride_id: int, lock: bool = False):
        statement = select(TaxiRide).where(TaxiRide.id == ride_id)
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    @staticmethod
    async def _driver_busy(session, driver_id: int, lock: bool = False) -> bool:
        statement = (
            select(TaxiRide.id)
            .where(
                TaxiRide.driver_id == driver_id,
                TaxiRide.status.in_(DRIVER_ACTIVE_STATUSES),
            )
            .limit(1)
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement) is not None
