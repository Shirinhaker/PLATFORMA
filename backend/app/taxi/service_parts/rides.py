"""Safarlar: chaqirish, qabul qilish, holat."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.orders.model import Order
from app.orders.notifications import append_order_notification
from app.profiles.model import BusinessProfile, UserProfile
from app.taxi.model import (
    ACTIVE_RIDE_STATUSES,
    DRIVER_ACTIVE_STATUSES,
    TaxiDriver,
    TaxiRide,
)
from app.taxi.schemas import (
    DriverRidesRead,
    MyRidesRead,
    RideAccepted,
    RideCreate,
    RideDriver,
    RideMutationRead,
    RidePerson,
    RideRead,
)
from app.taxi.service_parts.base import TaxiServiceBase
from app.taxi.service_parts.helpers import (
    COMMISSION_PER_ORDER,
    calculate_price,
)


class RidesMixin(TaxiServiceBase):
    async def create_ride(
        self, *, customer_account_id: int, body: RideCreate
    ) -> RideRead:
        if not body.ozim and not body.to_addr.strip():
            raise ApiError(
                400,
                "ride_destination_required",
                "Qayerga borishni kiriting yoki 'O'zim aytaman'ni tanlang.",
            )
        async with self._session_factory() as session:
            existing = await session.scalar(
                select(TaxiRide.id)
                .where(
                    TaxiRide.customer_account_id == customer_account_id,
                    TaxiRide.status.in_(ACTIVE_RIDE_STATUSES),
                )
                .limit(1)
            )
            if existing is not None:
                raise ApiError(
                    400, "active_ride_exists", "Sizda hali tugamagan zakaz bor."
                )
            now = self._now()
            ride = TaxiRide(
                legacy_source_id=None,
                customer_account_id=customer_account_id,
                driver_id=None,
                source_order_id=None,
                kind=body.kind,
                from_addr=body.from_addr.strip(),
                to_addr="" if body.ozim else body.to_addr.strip(),
                from_lat=body.from_lat,
                from_lng=body.from_lng,
                to_lat=None if body.ozim else body.to_lat,
                to_lng=None if body.ozim else body.to_lng,
                dist_km=body.dist_km,
                dur_min=body.dur_min,
                meter_km=None,
                ozim=body.ozim,
                cargo=body.cargo.strip(),
                car_type=body.car_type.strip(),
                note=body.note.strip(),
                status="pending",
                created_at=now,
                accepted_at=None,
                updated_at=now,
            )
            session.add(ride)
            try:
                await session.flush()
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ApiError(
                    400, "active_ride_exists", "Sizda hali tugamagan zakaz bor."
                ) from exc
            return await self._ride_read(session, ride)

    async def my_rides(self, *, customer_account_id: int) -> MyRidesRead:
        async with self._session_factory() as session:
            rows = list(
                (
                    await session.scalars(
                        select(TaxiRide)
                        .where(TaxiRide.customer_account_id == customer_account_id)
                        .order_by(TaxiRide.created_at.desc(), TaxiRide.id.desc())
                        .limit(100)
                    )
                ).all()
            )
            active = next(
                (row for row in rows if row.status in ACTIVE_RIDE_STATUSES), None
            )
            result = MyRidesRead(
                ride=await self._ride_read(session, active) if active else None,
                rides=[await self._ride_read(session, row) for row in rows],
            )
            await session.rollback()
            return result

    async def cancel_ride(
        self, *, customer_account_id: int, ride_id: int
    ) -> RideMutationRead:
        async with self._session_factory() as session:
            ride = await self._ride(session, ride_id, lock=True)
            if ride is None or ride.customer_account_id != customer_account_id:
                raise ApiError(404, "ride_not_found", "Zakaz topilmadi.")
            allowed = (
                {"pending", "accepted"}
                if ride.kind == "dostavka"
                else {"pending", "accepted", "arrived"}
            )
            if ride.status not in allowed:
                raise ApiError(
                    400, "ride_cancel_invalid", "Zakaz bu bosqichda bekor qilinmaydi."
                )
            ride.status = "canceled"
            ride.updated_at = self._now()
            available = True
            if ride.driver_id is not None:
                driver = await session.scalar(
                    select(TaxiDriver)
                    .where(TaxiDriver.id == ride.driver_id)
                    .with_for_update()
                )
                if driver is not None:
                    driver.available = True
                    driver.updated_at = ride.updated_at
            await session.commit()
            return RideMutationRead(status="canceled", available=available)

    async def pending_rides(self, *, user_account_id: int) -> DriverRidesRead:
        async with self._session_factory() as session:
            driver = await self._require_driver(session, user_account_id)
            current = await session.scalar(
                select(TaxiRide)
                .where(
                    TaxiRide.driver_id == driver.id,
                    TaxiRide.status.in_(DRIVER_ACTIVE_STATUSES),
                )
                .order_by(TaxiRide.created_at.desc())
                .limit(1)
            )
            if current is not None and driver.available:
                driver.available = False
                driver.updated_at = self._now()
                await session.commit()
            pending: list[TaxiRide] = []
            if driver.available and current is None:
                statement = select(TaxiRide).where(TaxiRide.status == "pending")
                if driver.service != "both":
                    statement = statement.where(TaxiRide.kind == driver.service)
                pending = list(
                    (
                        await session.scalars(
                            statement.order_by(TaxiRide.created_at, TaxiRide.id)
                        )
                    ).all()
                )
            result = DriverRidesRead(
                available=driver.available and current is None,
                current=await self._ride_read(session, current, include_customer=True)
                if current
                else None,
                pending=[
                    await self._ride_read(session, row, include_customer=True)
                    for row in pending
                ],
            )
            await session.rollback()
            return result

    async def accept_ride(self, *, user_account_id: int, ride_id: int) -> RideAccepted:
        async with self._session_factory() as session:
            # Lock order is stable across mutations: ride, then driver, then source order.
            ride = await self._ride(session, ride_id, lock=True)
            driver = await self._require_driver(session, user_account_id, lock=True)
            if ride is None or ride.status != "pending":
                raise ApiError(
                    409, "ride_already_taken", "Bu zakazni boshqa haydovchi oldi."
                )
            if not driver.available or await self._driver_busy(
                session, driver.id, lock=True
            ):
                raise ApiError(
                    400,
                    "driver_busy",
                    "Siz bandsiz. Joriy zakazni yakunlagach yangi zakaz olasiz.",
                )
            if driver.service not in {"both", ride.kind}:
                raise ApiError(
                    403,
                    "driver_service_mismatch",
                    "Bu zakaz siz tanlagan xizmat turiga mos emas.",
                )
            if driver.balance < COMMISSION_PER_ORDER:
                raise ApiError(
                    400,
                    "driver_balance_low",
                    "Balansingiz yetarli emas. Zakaz olish uchun balansni to'ldiring.",
                )
            now = self._now()
            ride.status = "accepted"
            ride.driver_id = driver.id
            ride.accepted_at = now
            ride.updated_at = now
            driver.balance -= COMMISSION_PER_ORDER
            driver.available = False
            driver.updated_at = now
            await self._sync_source_order(session, ride, "accepted")
            try:
                await session.flush()
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ApiError(
                    409, "ride_already_taken", "Bu zakazni boshqa haydovchi oldi."
                ) from exc
            return RideAccepted(
                ride=await self._ride_read(session, ride, include_customer=True),
                commission=COMMISSION_PER_ORDER,
                balance=driver.balance,
                available=False,
            )

    async def update_status(
        self, *, user_account_id: int, ride_id: int, new_status: str
    ) -> RideMutationRead:
        async with self._session_factory() as session:
            ride = await self._ride(session, ride_id, lock=True)
            driver = await self._require_driver(session, user_account_id, lock=True)
            if ride is None or ride.driver_id != driver.id:
                raise ApiError(404, "ride_not_found", "Zakaz topilmadi.")
            transitions = (
                {
                    "accepted": "arrived_store",
                    "arrived_store": "pickup_requested",
                    "in_delivery": "arrived_customer",
                    "arrived_customer": "delivered_waiting_customer",
                }
                if ride.kind == "dostavka"
                else {
                    "accepted": "arrived",
                    "arrived": "ongoing",
                    "ongoing": "completed",
                }
            )
            if transitions.get(ride.status) != new_status:
                raise ApiError(
                    400, "ride_status_invalid", "Bu bosqichga o'tib bo'lmaydi."
                )
            ride.status = new_status
            ride.updated_at = self._now()
            driver.available = new_status == "completed"
            driver.updated_at = ride.updated_at
            await self._sync_source_order(session, ride, new_status)
            await session.commit()
            return RideMutationRead(status=new_status, available=driver.available)

    async def update_progress(
        self, *, user_account_id: int, ride_id: int, km: float
    ) -> RideRead:
        async with self._session_factory() as session:
            ride = await self._ride(session, ride_id, lock=True)
            driver = await self._require_driver(session, user_account_id, lock=True)
            if ride is None or ride.driver_id != driver.id:
                raise ApiError(404, "ride_not_found", "Zakaz topilmadi.")
            if ride.status != "ongoing":
                raise ApiError(
                    400,
                    "ride_progress_invalid",
                    "Hisoblagich faqat safar davomida ishlaydi.",
                )
            ride.meter_km = km
            ride.updated_at = self._now()
            await session.commit()
            return await self._ride_read(session, ride, include_customer=True)

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
    async def _ride(session, ride_id: int, lock: bool = False):
        statement = select(TaxiRide).where(TaxiRide.id == ride_id)
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)
