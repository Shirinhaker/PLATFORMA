"""Reklama joylash: narx, yaratish, ro'yxat va to'lovdan keyin yoqish.

v1656 (`api.py:3999-4180`, `payment_api.py:864`) bilan bir xil oqim:

    hudud va davomiylik tanlanadi → narx hisoblanadi
    → reklama `payment_pending` bilan yaratiladi
    → foydalanuvchi to'laydi, admin tasdiqlaydi
    → jadval suriladi va reklama `active` bo'ladi

Migratsiyagacha reklama kabinet JSON'iga tushardi, public reklamalar esa
relatsion jadvaldan o'qilardi — ya'ni yangi reklama hech qachon bosh
sahifada chiqmasdi.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import AccountType
from app.advertisements.model import Advertisement
from app.advertisements.pricing import (
    VALID_AD_DURATIONS,
    AdPricingError,
    calculate_ad_price,
    first_schedule_start,
    full_hour,
    schedule_end_at,
    shift_schedule_start,
)
from app.advertisements.schemas import (
    AdvertisementCreate,
    AdvertisementQuote,
    AdvertisementQuoteRequest,
    AdvertisementRates,
    AdvertisementRead,
    AdvertisementTarget,
)
from app.core.errors import ApiError
from app.legacy_migration.model import ReviewState
from app.payments.model import PlatformPrice


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]

PRICE_CODE = "advertisement_district_hour"
DEFAULT_HOUR_RATE = 20_000
RATE_NOTE = (
    "Reklama kvitansiya yuborilib, administrator tasdiqlagandan keyin "
    "faol bo'ladi."
)


def _unix(value: datetime | None) -> int:
    if value is None:
        return 0
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return int(aware.timestamp())


def _moment(stamp: int) -> datetime:
    return datetime.fromtimestamp(stamp, UTC)


def _clock(value: time | None, fallback: str) -> str:
    return value.strftime("%H:%M") if value is not None else fallback


def _targets(raw: Any) -> list[AdvertisementTarget]:
    rows = raw if isinstance(raw, list) else []
    result = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        result.append(AdvertisementTarget(
            level=str(item.get("level") or "republic"),
            region=str(item.get("region") or ""),
            district=str(item.get("district") or ""),
        ))
    return result


class AdvertisementService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        image_url_provider: Callable[[str], str],
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._image_url = image_url_provider
        self._now = now_provider

    # ------------------------------------------------------------- narxlar

    async def rates(self) -> AdvertisementRates:
        async with self._session_factory() as session:
            rate = await self._hour_rate(session)
            await session.rollback()
        return AdvertisementRates(
            price_code=PRICE_CODE,
            district_hour_rate=rate,
            duration_days=list(VALID_AD_DURATIONS),
            note=RATE_NOTE,
        )

    async def quote(
        self, body: AdvertisementQuoteRequest
    ) -> AdvertisementQuote:
        async with self._session_factory() as session:
            rate = await self._hour_rate(session)
            await session.rollback()
        pricing = self._price(body, rate)
        return AdvertisementQuote(**{
            key: pricing[key]
            for key in (
                "district_count", "hours_per_day", "duration_days",
                "district_hour_rate", "billable_district_hours",
                "total", "currency",
            )
        })

    # ------------------------------------------------------------- yaratish

    async def create(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: AdvertisementCreate,
    ) -> AdvertisementRead:
        now = self._now()
        async with self._session_factory() as session:
            rate = await self._hour_rate(session)
            pricing = self._price(body, rate)
            try:
                start_at = first_schedule_start(
                    start_date=body.start_date,
                    daily_all_day=body.daily_all_day,
                    daily_start=body.daily_start,
                )
                end_at = schedule_end_at(
                    actual_start_at=start_at,
                    duration_days=pricing["duration_days"],
                    hours_each_day=pricing["hours_per_day"],
                    daily_all_day=body.daily_all_day,
                )
            except AdPricingError as exc:
                raise ApiError(400, "advertisement_schedule_invalid", str(exc))

            advertisement = Advertisement(
                owner_user_account_id=(
                    account_id if account_type is AccountType.USER else None
                ),
                owner_business_account_id=(
                    account_id if account_type is AccountType.BUSINESS else None
                ),
                actor_type=account_type.value,
                title=body.title.strip(),
                caption=body.caption.strip(),
                desktop_image_object_key=body.desktop_image_object_key,
                mobile_image_object_key=body.mobile_image_object_key,
                crop_x=body.crop_x,
                crop_y=body.crop_y,
                crop_zoom=body.crop_zoom,
                daily_all_day=body.daily_all_day,
                daily_start=self._time(body.daily_start),
                daily_end=self._time(body.daily_end),
                targets_json=pricing["targets"],
                placement=body.placement,
                start_at=_moment(start_at),
                end_at=_moment(end_at),
                duration_days=pricing["duration_days"],
                price=pricing["total"],
                district_count=pricing["district_count"],
                hours_per_day=pricing["hours_per_day"],
                district_hour_rate=pricing["district_hour_rate"],
                billable_district_hours=pricing["billable_district_hours"],
                price_code=PRICE_CODE,
                # To'lov tasdiqlanmaguncha reklama ko'rinmaydi.
                status="payment_pending",
                views=0,
                clicks=0,
                review_state=ReviewState.READY,
                migration_run_id=None,
                created_at=now,
                updated_at=now,
            )
            session.add(advertisement)
            await session.flush()
            result = self._read(advertisement)
            await session.commit()
        return result

    async def list_mine(
        self, *, account_id: int, account_type: AccountType
    ) -> list[AdvertisementRead]:
        column = (
            Advertisement.owner_user_account_id
            if account_type is AccountType.USER
            else Advertisement.owner_business_account_id
        )
        async with self._session_factory() as session:
            rows = list((await session.scalars(
                select(Advertisement)
                .where(column == account_id)
                .order_by(Advertisement.id.desc())
                .limit(200)
            )).all())
            result = [self._read(row) for row in rows]
            await session.rollback()
        return result

    async def delete(
        self, *, account_id: int, account_type: AccountType, advertisement_id: int
    ) -> None:
        async with self._session_factory() as session:
            advertisement = await self._require_own(
                session,
                account_id=account_id,
                account_type=account_type,
                advertisement_id=advertisement_id,
            )
            await session.delete(advertisement)
            await session.commit()

    # ----------------------------------------------------- to'lovdan keyin

    async def activate_paid(
        self,
        session: AsyncSession,
        *,
        advertisement_id: int,
        account_id: int,
        now: int,
    ) -> None:
        """To'lov tasdiqlangach jadvalni suradi va reklamani yoqadi.

        Chaqiruvchining tranzaksiyasida ishlaydi — to'lov holati va
        reklama birga yoziladi.
        """
        advertisement = await session.scalar(
            select(Advertisement)
            .where(Advertisement.id == advertisement_id)
            .with_for_update()
        )
        if advertisement is None or advertisement.status != "payment_pending":
            raise ApiError(
                409,
                "advertisement_not_pending",
                "Kutilayotgan reklama topilmadi.",
            )
        owner = (
            advertisement.owner_user_account_id
            or advertisement.owner_business_account_id
        )
        if owner != account_id:
            raise ApiError(
                409,
                "advertisement_owner_mismatch",
                "Reklama to‘lov egasiga tegishli emas.",
            )
        daily_start = _clock(advertisement.daily_start, "00:00")
        try:
            actual_start = shift_schedule_start(
                requested_start_at=_unix(advertisement.start_at),
                approved_at=now,
                daily_all_day=advertisement.daily_all_day,
                daily_start=daily_start,
            )
            actual_end = schedule_end_at(
                actual_start_at=actual_start,
                duration_days=advertisement.duration_days,
                hours_each_day=advertisement.hours_per_day,
                daily_all_day=advertisement.daily_all_day,
            )
        except AdPricingError as exc:
            raise ApiError(
                400, "advertisement_schedule_invalid", str(exc)
            ) from exc
        advertisement.status = "active"
        advertisement.start_at = _moment(actual_start)
        advertisement.end_at = _moment(actual_end)
        advertisement.updated_at = _moment(now)

    # ------------------------------------------------------------ yordamchi

    @staticmethod
    def _time(value: str) -> time:
        return time(hour=full_hour(value))

    @staticmethod
    def _price(
        body: AdvertisementQuoteRequest, rate: int
    ) -> dict[str, Any]:
        try:
            return calculate_ad_price(
                targets=[target.model_dump() for target in body.targets],
                duration_days=body.duration_days,
                daily_all_day=body.daily_all_day,
                daily_start=body.daily_start,
                daily_end=body.daily_end,
                district_hour_rate=rate,
            )
        except AdPricingError as exc:
            raise ApiError(400, "advertisement_price_invalid", str(exc))

    @staticmethod
    async def _hour_rate(session: AsyncSession) -> int:
        """Narx admin panelidan boshqariladi."""
        rate = await session.scalar(
            select(PlatformPrice.amount_uzs).where(
                PlatformPrice.price_code == PRICE_CODE,
                PlatformPrice.active == 1,
            )
        )
        return int(rate) if rate else DEFAULT_HOUR_RATE

    @staticmethod
    async def _require_own(
        session: AsyncSession,
        *,
        account_id: int,
        account_type: AccountType,
        advertisement_id: int,
    ) -> Advertisement:
        column = (
            Advertisement.owner_user_account_id
            if account_type is AccountType.USER
            else Advertisement.owner_business_account_id
        )
        advertisement = await session.scalar(
            select(Advertisement).where(
                Advertisement.id == advertisement_id,
                column == account_id,
            )
        )
        if advertisement is None:
            raise ApiError(
                404, "advertisement_not_found", "Reklama topilmadi."
            )
        return advertisement

    def _read(self, row: Advertisement) -> AdvertisementRead:
        return AdvertisementRead(
            id=row.id,
            title=row.title,
            caption=row.caption,
            targets=_targets(row.targets_json),
            placement=row.placement,
            status=row.status,
            daily_all_day=row.daily_all_day,
            daily_start=_clock(row.daily_start, "00:00"),
            daily_end=_clock(row.daily_end, "00:00"),
            duration_days=row.duration_days,
            district_count=row.district_count,
            hours_per_day=row.hours_per_day,
            district_hour_rate=row.district_hour_rate,
            billable_district_hours=row.billable_district_hours,
            price=row.price,
            price_code=row.price_code,
            start_at=_unix(row.start_at),
            end_at=_unix(row.end_at),
            views=row.views,
            clicks=row.clicks,
            desktop_image_url=self._image_url(row.desktop_image_object_key),
            mobile_image_url=self._image_url(row.mobile_image_object_key),
            created_at=_unix(row.created_at),
        )
