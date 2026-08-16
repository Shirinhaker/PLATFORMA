"""Ro'yxatlar: biznes navbati va mening navbatlarim."""

from __future__ import annotations

from datetime import date

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.queues.schemas import (
    QueueEntryRead,
)
from app.queues.service_parts.base import QueueServiceBase


class ListingMixin(QueueServiceBase):
    async def list_business(
        self,
        *,
        business_account_id: int,
        queue_date: date | None,
    ) -> list[QueueEntryRead]:
        async with self._session_factory() as session:
            await self._business(session, business_account_id)
            rows = await self._repository.list_business(
                session,
                business_account_id=business_account_id,
                queue_date=queue_date or self._local_now().date(),
            )
            response = [self._entry_read(*row) for row in rows]
            await session.rollback()
            return response

    async def list_mine(
        self,
        *,
        account_id: int,
        account_type: AccountType,
    ) -> list[QueueEntryRead]:
        if account_type is not AccountType.USER:
            raise ApiError(403, "queue_user_required", "Avval oddiy profilga o'ting.")
        async with self._session_factory() as session:
            rows = await self._repository.list_mine(
                session,
                customer_account_id=account_id,
            )
            response = [self._entry_read(*row) for row in rows]
            await session.rollback()
            return response
