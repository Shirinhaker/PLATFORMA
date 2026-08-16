"""Haydovchilar: kartochka, bandlik, balans."""

from __future__ import annotations

from sqlalchemy import select

from app.admin.audit import append_audit
from app.core.errors import ApiError
from app.profiles.model import UserProfile
from app.taxi.model import (
    TaxiDriver,
)
from app.taxi.schemas import (
    AdminDriverRead,
    DriverRead,
    DriverWrite,
)
from app.taxi.service_parts.base import TaxiServiceBase
from app.taxi.service_parts.helpers import (
    COMMISSION_PER_ORDER,
    PRICING,
)


class DriversMixin(TaxiServiceBase):
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
        if body.service in {"taxi", "both"} and not all(
            (car_model, car_color, car_plate)
        ):
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
            return self._driver_read(
                driver, profile, await self._driver_busy(session, driver.id)
            )

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

    async def list_admin_drivers(self) -> list[AdminDriverRead]:
        async with self._session_factory() as session:
            rows = list(
                (
                    await session.execute(
                        select(TaxiDriver, UserProfile)
                        .join(
                            UserProfile,
                            UserProfile.account_id == TaxiDriver.user_account_id,
                        )
                        .order_by(UserProfile.name, TaxiDriver.id)
                    )
                ).all()
            )
            result = [
                AdminDriverRead(
                    id=driver.id,
                    name=profile.name,
                    phone=driver.phone,
                    balance=driver.balance,
                    service=driver.service,
                    available=driver.available,
                )
                for driver, profile in rows
            ]
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
