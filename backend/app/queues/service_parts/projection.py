"""Navbat javoblarini API shakliga aylantirish.

Bu metodlar bir necha mixin'ga kerak, shuning uchun `base.py` da
turardi va uni savatga aylantirardi. Endi alohida — `Base` shundan
meros oladi, ya'ni chaqiruv joylari o'zgarmaydi.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.model import CatalogItem
from app.core.errors import ApiError
from app.public_ids import build_content_public_id
from app.queues.model import QueueEntry, QueueProvider
from app.queues.repository import ACTIVE_STATUSES
from app.queues.schemas import (
    QueueEntryRead,
    QueueProviderRead,
)
from app.queues.service_parts.helpers import (
    _clock_text,
)


class QueueProjectionMixin:
    def _provider_read(
        self,
        provider: QueueProvider,
        items: list[CatalogItem],
        *,
        queue_count: int = 0,
    ) -> QueueProviderRead:
        return QueueProviderRead(
            id=provider.id,
            staff_id=provider.legacy_staff_id,
            name=provider.staff_name_snapshot,
            profession=provider.profession_snapshot,
            specialty=provider.specialty,
            experience_years=provider.experience_years,
            qualification=provider.qualification,
            work_days=provider.work_days,
            work_start=_clock_text(provider.work_start),
            work_end=_clock_text(provider.work_end),
            avg_minutes=provider.avg_minutes,
            room=provider.room,
            bio=provider.bio,
            status=provider.status,
            mode=provider.mode,
            item_public_ids=[self._item_public_id(item) for item in items],
            queue_count=queue_count,
        )

    def _entry_read(
        self,
        entry: QueueEntry,
        avg_minutes: int,
        ahead_count: int,
        business_name: str,
        business_direction: str,
    ) -> QueueEntryRead:
        active = entry.status in ACTIVE_STATUSES
        ahead = int(ahead_count or 0) if active else 0
        average = int(avg_minutes or 0)
        return QueueEntryRead(
            id=entry.id,
            business_account_id=entry.business_account_id,
            business_name=str(business_name or ""),
            business_direction=str(business_direction or ""),
            customer_account_id=entry.customer_account_id,
            item_public_id=(
                build_content_public_id("service", entry.catalog_item_id)
                if entry.catalog_item_id is not None
                else ""
            ),
            provider_id=entry.provider_id,
            patient_name=entry.patient_name,
            phone=entry.phone,
            service_name=entry.service_name_snapshot,
            provider_name=entry.provider_name_snapshot,
            queue_date=entry.queue_date,
            queue_no=entry.queue_no,
            queue_code=entry.queue_code,
            source=entry.source,
            status=entry.status,
            note=entry.note,
            slot_time=_clock_text(entry.slot_time),
            ahead_count=ahead,
            avg_minutes=average,
            wait_minutes=ahead * average if active and average > 0 else 0,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )

    async def _project(
        self,
        session: AsyncSession,
        queue_id: int,
    ) -> QueueEntryRead:
        row = await self._repository.projected_entry(session, queue_id)
        if row is None:
            raise ApiError(404, "queue_not_found", "Navbat topilmadi.")
        return self._entry_read(*row)

    @staticmethod
    def _item_public_id(item: CatalogItem) -> str:
        return item.public_id or build_content_public_id(item.kind, item.id)
