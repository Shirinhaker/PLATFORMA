"""Bo'sh vaqtlar: variantlar va slotlar."""

from __future__ import annotations

from datetime import date

from app.queues.schemas import (
    QueueOptionsRead,
    QueueSlotsRead,
)
from app.queues.service_parts.base import QueueServiceBase
from app.queues.service_parts.helpers import (
    _clock_text,
    _generated_slots,
    _slot_minutes,
)


class AvailabilityMixin(QueueServiceBase):
    async def options(
        self,
        *,
        business_public_id: str,
        item_public_id: str,
        queue_date: date | None,
    ) -> QueueOptionsRead:
        async with self._session_factory() as session:
            resolved_date = queue_date or self._local_now().date()
            business, item = await self._public_context(
                session, business_public_id, item_public_id
            )
            self._validate_date(resolved_date)
            rows = await self._repository.provider_options(
                session,
                business_account_id=business.account_id,
                catalog_item_id=item.id,
                queue_date=resolved_date,
            )
            links = await self._repository.provider_links(
                session, [provider.id for provider, _count in rows]
            )
            active_staff = await self._staff_rows(session, business)
            if await self._staff_source_exists(session, business):
                active_staff_ids = {int(row["id"]) for row in active_staff}
                rows = [
                    row for row in rows if row[0].legacy_staff_id in active_staff_ids
                ]
            response = QueueOptionsRead(
                business_public_id=business_public_id,
                item_public_id=item_public_id,
                queue_date=resolved_date,
                providers=[
                    self._provider_read(
                        provider,
                        links.get(provider.id, []),
                        queue_count=int(count or 0),
                    )
                    for provider, count in rows
                ],
            )
            await session.rollback()
            return response

    async def slots(
        self,
        *,
        business_public_id: str,
        item_public_id: str,
        provider_id: int,
        queue_date: date | None,
    ) -> QueueSlotsRead:
        async with self._session_factory() as session:
            resolved_date = queue_date or self._local_now().date()
            business, item = await self._public_context(
                session, business_public_id, item_public_id
            )
            provider = await self._provider_context(
                session, business, item, provider_id
            )
            self._validate_date(resolved_date)
            if provider.mode != "slot":
                response = QueueSlotsRead(mode="live", slots=[])
                await session.rollback()
                return response
            if not self._works_on(provider, resolved_date):
                response = QueueSlotsRead(mode="slot", slots=[])
                await session.rollback()
                return response
            taken = await self._repository.taken_slots(
                session,
                catalog_item_id=item.id,
                provider_id=provider.id,
                queue_date=resolved_date,
            )
            local_now = self._local_now()
            values = [
                value
                for value in _generated_slots(
                    provider.work_start,
                    provider.work_end,
                    provider.avg_minutes,
                )
                if value not in taken
                and not (
                    resolved_date == local_now.date()
                    and _slot_minutes(value) <= local_now.hour * 60 + local_now.minute
                )
            ]
            response = QueueSlotsRead(
                mode="slot",
                slots=[_clock_text(value) for value in values],
            )
            await session.rollback()
            return response
