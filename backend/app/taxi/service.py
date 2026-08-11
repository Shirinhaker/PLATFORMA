from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
import math

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.audit import append_audit
from app.core.errors import ApiError
from app.notifications.repository import NotificationRepository
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
    AdminDriverRead,
    DriverRead,
    DriverRidesRead,
    DriverWrite,
    MyRidesRead,
    RideAccepted,
    RideCreate,
    RideDriver,
    RideMutationRead,
    RidePerson,
    RideRead,
)


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NowProvider = Callable[[], datetime]
PRICING = {
    "taxi": {"base": 5_000, "per_km": 2_000, "min": 9_000},
    "dostavka": {"base": 10_000, "per_km": 2_500, "min": 15_000},
}
COMMISSION_PER_ORDER = 1_000


def calculate_price(kind: str, distance_km: float | None) -> int | None:
    if distance_km is None or distance_km <= 0:
        return None
    config = PRICING.get(kind, PRICING["taxi"])
    price = max(config["min"], config["base"] + config["per_km"] * distance_km)
    return int(price / 500 + 0.5) * 500


class TaxiService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._now = now_provider or (lambda: datetime.now(UTC))
        self._notifications = NotificationRepository()

    @staticmethod
    def pricing() -> dict[str, object]:
        return {"pricing": PRICING, "commission": COMMISSION_PER_ORDER}

    async def get_driver(self, *, user_account_id: int) -> DriverRead:
        async with self._session_factory() as session:
            driver = await self._driver_for_user(session, user_account_id)
            profile = await session.get(UserProfile, user_account_id)
            if driver is None:
                result = DriverRead(exists=False, name=profile.name if profile else "")
                await session.rollback()
                return result
            busy = await self._driver_busy(session, driver.id)
            result = self._driver_read(driver, profile, busy)
            await session.rollback()
            return result

    async def save_driver(
        self, *, user_account_id: int, body: DriverWrite
    ) -> DriverRead:
        phone = body.phone.strip()
        car_model = body.car_model.strip()
        car_color = body.car_color.strip()
        car_plate = body.car_plate.strip()
        if not phone:
            raise ApiError(400, "driver_phone_required", "Telefon raqamini kiriting.")
        if body.service in {"taxi", "both"} and not all((car_model, car_color, car_plate)):
            raise ApiError(
                400,
                "driver_car_required",
                "Taxi uchun mashina rusumi, raqami va rangini to'ldiring.",
            )
        async with self._session_factory() as session:
            driver = await self._driver_for_user(session, user_account_id, lock=True)
            now = self._now()
            if driver is None:
                driver = TaxiDriver(
                    legacy_source_id=None,
                    user_account_id=user_account_id,
                    phone=phone,
                    car_model=car_model,
                    car_color=car_color,
                    car_plate=car_plate,
                    service=body.service,
                    available=True,
                    rating_sum=0,
                    rating_count=0,
                    balance=0,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
                session.add(driver)
            else:
                driver.phone = phone
                driver.car_model = car_model
                driver.car_color = car_color
                driver.car_plate = car_plate
                driver.service = body.service
                driver.updated_at = now
            await session.flush()
            profile = await session.get(UserProfile, user_account_id)
            await session.commit()
            return self._driver_read(driver, profile, await self._driver_busy(session, driver.id))

    async def set_availability(
        self, *, user_account_id: int, available: bool
    ) -> DriverRead:
        async with self._session_factory() as session:
            driver = await self._require_driver(session, user_account_id)
            busy = await self._driver_busy(session, driver.id, lock=True)
            driver = await self._require_driver(session, user_account_id, lock=True)
            if available and busy:
                raise ApiError(
                    400,
                    "driver_active_ride",
                    "Joriy zakazni yakunlamaguningizcha yangi zakaz ololmaysiz.",
                )
            driver.available = available
            driver.updated_at = self._now()
            profile = await session.get(UserProfile, user_account_id)
            await session.commit()
            return self._driver_read(driver, profile, busy)

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
                select(TaxiRide.id).where(
                    TaxiRide.customer_account_id == customer_account_id,
                    TaxiRide.status.in_(ACTIVE_RIDE_STATUSES),
                ).limit(1)
            )
            if existing is not None:
                raise ApiError(400, "active_ride_exists", "Sizda hali tugamagan zakaz bor.")
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
                raise ApiError(400, "active_ride_exists", "Sizda hali tugamagan zakaz bor.") from exc
            return await self._ride_read(session, ride)

    async def my_rides(self, *, customer_account_id: int) -> MyRidesRead:
        async with self._session_factory() as session:
            rows = list((await session.scalars(
                select(TaxiRide)
                .where(TaxiRide.customer_account_id == customer_account_id)
                .order_by(TaxiRide.created_at.desc(), TaxiRide.id.desc())
                .limit(100)
            )).all())
            active = next((row for row in rows if row.status in ACTIVE_RIDE_STATUSES), None)
            result = MyRidesRead(
                ride=await self._ride_read(session, active) if active else None,
                rides=[await self._ride_read(session, row) for row in rows],
            )
            await session.rollback()
            return result

    async def cancel_ride(self, *, customer_account_id: int, ride_id: int) -> RideMutationRead:
        async with self._session_factory() as session:
            ride = await self._ride(session, ride_id, lock=True)
            if ride is None or ride.customer_account_id != customer_account_id:
                raise ApiError(404, "ride_not_found", "Zakaz topilmadi.")
            allowed = {"pending", "accepted"} if ride.kind == "dostavka" else {"pending", "accepted", "arrived"}
            if ride.status not in allowed:
                raise ApiError(400, "ride_cancel_invalid", "Zakaz bu bosqichda bekor qilinmaydi.")
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
                pending = list((await session.scalars(
                    statement.order_by(TaxiRide.created_at, TaxiRide.id)
                )).all())
            result = DriverRidesRead(
                available=driver.available and current is None,
                current=await self._ride_read(session, current, include_customer=True) if current else None,
                pending=[await self._ride_read(session, row, include_customer=True) for row in pending],
            )
            await session.rollback()
            return result

    async def accept_ride(self, *, user_account_id: int, ride_id: int) -> RideAccepted:
        async with self._session_factory() as session:
            # Lock order is stable across mutations: ride, then driver, then source order.
            ride = await self._ride(session, ride_id, lock=True)
            driver = await self._require_driver(session, user_account_id, lock=True)
            if ride is None or ride.status != "pending":
                raise ApiError(409, "ride_already_taken", "Bu zakazni boshqa haydovchi oldi.")
            if not driver.available or await self._driver_busy(session, driver.id, lock=True):
                raise ApiError(400, "driver_busy", "Siz bandsiz. Joriy zakazni yakunlagach yangi zakaz olasiz.")
            if driver.service not in {"both", ride.kind}:
                raise ApiError(403, "driver_service_mismatch", "Bu zakaz siz tanlagan xizmat turiga mos emas.")
            if driver.balance < COMMISSION_PER_ORDER:
                raise ApiError(400, "driver_balance_low", "Balansingiz yetarli emas. Zakaz olish uchun balansni to'ldiring.")
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
                raise ApiError(409, "ride_already_taken", "Bu zakazni boshqa haydovchi oldi.") from exc
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
                else {"accepted": "arrived", "arrived": "ongoing", "ongoing": "completed"}
            )
            if transitions.get(ride.status) != new_status:
                raise ApiError(400, "ride_status_invalid", "Bu bosqichga o'tib bo'lmaydi.")
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
                raise ApiError(400, "ride_progress_invalid", "Hisoblagich faqat safar davomida ishlaydi.")
            ride.meter_km = km
            ride.updated_at = self._now()
            await session.commit()
            return await self._ride_read(session, ride, include_customer=True)

    async def list_admin_drivers(self) -> list[AdminDriverRead]:
        async with self._session_factory() as session:
            rows = list((await session.execute(
                select(TaxiDriver, UserProfile)
                .join(UserProfile, UserProfile.account_id == TaxiDriver.user_account_id)
                .order_by(UserProfile.name, TaxiDriver.id)
            )).all())
            result = [AdminDriverRead(
                id=driver.id,
                name=profile.name,
                phone=driver.phone,
                balance=driver.balance,
                service=driver.service,
                available=driver.available,
            ) for driver, profile in rows]
            await session.rollback()
            return result

    async def topup_driver(
        self,
        *,
        driver_id: int,
        amount: int,
        admin_tg_id: int,
        reason: str,
        meta: dict[str, str],
    ) -> tuple[int, int]:
        async with self._session_factory() as session:
            driver = await session.scalar(
                select(TaxiDriver).where(TaxiDriver.id == driver_id).with_for_update()
            )
            if driver is None:
                raise ApiError(404, "driver_not_found", "Haydovchi topilmadi.")
            before = driver.balance
            now = self._now()
            driver.balance += amount
            driver.updated_at = now
            await append_audit(
                session,
                admin_tg_id=admin_tg_id,
                action="taxi.driver_balance_topup",
                target_kind="taxi_driver",
                target_id=driver.id,
                before={"balance": before},
                after={"balance": driver.balance, "amount": amount},
                reason=reason,
                meta=meta,
                now=now,
            )
            await session.commit()
            return driver.id, driver.balance

    async def after_order_handoff(self, session: AsyncSession, order_id: int) -> None:
        ride = await session.scalar(
            select(TaxiRide).where(
                TaxiRide.source_order_id == order_id,
                TaxiRide.kind == "dostavka",
            ).with_for_update()
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
        session.add(TaxiRide(
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
            note=f"Do'kon buyurtmasi #{order.id}" + (f" — {order.title}" if order.title else ""),
            status="pending",
            created_at=now,
            accepted_at=None,
            updated_at=now,
        ))
        await session.flush()

    async def after_order_received(self, session: AsyncSession, order_id: int) -> None:
        ride = await session.scalar(
            select(TaxiRide).where(
                TaxiRide.source_order_id == order_id,
                TaxiRide.kind == "dostavka",
            ).with_for_update()
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
            driver = await session.get(TaxiDriver, ride.driver_id) if ride.driver_id else None
            profile = await session.get(UserProfile, driver.user_account_id) if driver else None
            name = profile.name if profile else "Dostavkachi"
            await append_order_notification(
                session, self._notifications, order,
                side="customer", event="courier_assigned",
                title="Dostavkachi buyurtmani qabul qildi", body=name,
            )
            await append_order_notification(
                session, self._notifications, order,
                side="provider", event="courier_assigned",
                title="Dostavkachi biriktirildi", body=name,
            )
        elif ride_status == "pickup_requested":
            await append_order_notification(
                session, self._notifications, order,
                side="provider", event="courier_pickup_requested",
                title="Dostavkachi buyurtmani olishga tayyor",
                body="Buyurtmani dostavkachiga topshiring.",
                action_type="confirm_handoff",
            )
        elif ride_status == "arrived_customer":
            await append_order_notification(
                session, self._notifications, order,
                side="customer", event="courier_arrived",
                title="Dostavkachi yetib keldi",
                body="Buyurtmani qabul qilishga tayyorlaning.",
            )
        elif ride_status == "delivered_waiting_customer":
            await append_order_notification(
                session, self._notifications, order,
                side="customer", event="delivery_handed",
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
            profile = await session.get(UserProfile, driver.user_account_id) if driver else None
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
            + math.cos(lat1 * radians) * math.cos(lat2 * radians)
            * math.sin(delta_lng / 2) ** 2
        )
        return round(6371 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value)), 1)

    @staticmethod
    def _driver_read(driver: TaxiDriver, profile: UserProfile | None, busy: bool) -> DriverRead:
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
        statement = select(TaxiDriver).where(TaxiDriver.user_account_id == user_account_id)
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def _require_driver(self, session, user_account_id: int, lock: bool = False):
        driver = await self._driver_for_user(session, user_account_id, lock)
        if driver is None:
            raise ApiError(403, "driver_required", "Avval haydovchi sifatida ro'yxatdan o'ting.")
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
        statement = select(TaxiRide.id).where(
            TaxiRide.driver_id == driver_id,
            TaxiRide.status.in_(DRIVER_ACTIVE_STATUSES),
        ).limit(1)
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement) is not None
