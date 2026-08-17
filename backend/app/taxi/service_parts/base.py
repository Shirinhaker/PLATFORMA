"""Umumiy asos: haydovchi/safar yuklash, masofa hisobi, javob shakli."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.core.errors import ApiError
from app.notifications.repository_parts import NotificationRepository
from app.taxi.model import (
    DRIVER_ACTIVE_STATUSES,
    TaxiDriver,
    TaxiRide,
)
from app.taxi.service_parts.helpers import (
    NowProvider,
    SessionFactory,
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
