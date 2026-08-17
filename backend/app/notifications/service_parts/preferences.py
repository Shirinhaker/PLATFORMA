"""Sozlamalar va filtrlar."""

from __future__ import annotations

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.notifications.schemas import (
    NotificationFilterRead,
    NotificationFilterWrite,
    NotificationMutationRead,
    NotificationPreferenceRead,
    NotificationPreferenceWrite,
)
from app.notifications.service_parts.base import NotificationServiceBase


class PreferencesMixin(NotificationServiceBase):
    async def preference(
        self,
        *,
        account_id: int,
        account_type: AccountType,
    ) -> NotificationPreferenceRead:
        async with self._session_factory() as session:
            row = await self._repository.preference(
                session,
                account_id=account_id,
                account_type=account_type.value,
            )
            if row is None:
                return NotificationPreferenceRead()
            return NotificationPreferenceRead(
                enabled=bool(row.enabled),
                orders_enabled=bool(row.orders_enabled),
            )

    async def save_preference(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: NotificationPreferenceWrite,
    ) -> NotificationPreferenceRead:
        async with self._session_factory() as session:
            await self._repository.save_preference(
                session,
                account_id=account_id,
                account_type=account_type.value,
                enabled=body.enabled,
                orders_enabled=body.orders_enabled,
                updated_at=self._now(),
            )
            await session.commit()
            return NotificationPreferenceRead(**body.model_dump())

    async def filters(
        self,
        *,
        account_id: int,
        account_type: AccountType,
    ) -> list[NotificationFilterRead]:
        async with self._session_factory() as session:
            rows = await self._repository.filters(
                session,
                account_id=account_id,
                account_type=account_type.value,
            )
            return [self._filter_read(row) for row in rows]

    async def add_filter(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: NotificationFilterWrite,
    ) -> NotificationFilterRead:
        async with self._session_factory() as session:
            row = await self._repository.add_filter(
                session,
                account_id=account_id,
                account_type=account_type.value,
                category=body.cat,
                region=body.region,
                district=body.district,
                price_min=body.price_min,
                price_max=body.price_max,
                keyword=body.keyword,
                created_at=self._now(),
            )
            await session.commit()
            return self._filter_read(row)

    async def remove_filter(
        self,
        *,
        filter_id: int,
        account_id: int,
        account_type: AccountType,
    ) -> NotificationMutationRead:
        async with self._session_factory() as session:
            removed = await self._repository.remove_filter(
                session,
                account_id=account_id,
                account_type=account_type.value,
                filter_id=filter_id,
            )
            if not removed:
                raise ApiError(
                    404,
                    "notification_filter_not_found",
                    "Filtr topilmadi.",
                )
            await session.commit()
            return NotificationMutationRead()
