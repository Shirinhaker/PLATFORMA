"""Umumiy asos: bog'liqliklar, kontekst yuklash, javob shakli."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.model import CatalogItem
from app.core.errors import ApiError
from app.notifications.repository import NotificationRepository
from app.profiles.model import BusinessProfile
from app.public_ids import build_content_public_id
from app.queues.model import QueueEntry, QueueProvider
from app.queues.repository import ACTIVE_STATUSES, QueueRepository
from app.queues.schemas import (
    QueueEntryRead,
    QueueProviderRead,
    QueueProviderWrite,
)
from app.queues.service_parts.helpers import (
    QUEUE_DIRECTIONS,
    UZBEKISTAN_TZ,
    NowProvider,
    SessionFactory,
    _clock,
    _clock_text,
)
from app.staff.repository import StaffRepository


class QueueServiceBase:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: QueueRepository | None = None,
        staff_repository: StaffRepository | None = None,
        notification_repository: NotificationRepository | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or QueueRepository()
        self._staff_repository = staff_repository or StaffRepository()
        self._notifications = notification_repository or NotificationRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def _public_context(
        self,
        session: AsyncSession,
        business_public_id: str,
        item_public_id: str,
    ) -> tuple[BusinessProfile, CatalogItem]:
        business = await self._repository.business_by_public_id(
            session, business_public_id
        )
        if business is None:
            raise ApiError(404, "queue_business_not_found", "Biznes profil topilmadi.")
        self._require_direction(business)
        item = await self._enabled_item(session, business.account_id, item_public_id)
        return business, item

    async def _business(
        self,
        session: AsyncSession,
        account_id: int,
    ) -> BusinessProfile:
        business = await self._repository.business(session, account_id)
        if business is None:
            raise ApiError(404, "queue_business_not_found", "Biznes profil topilmadi.")
        self._require_direction(business)
        return business

    def _require_direction(self, business: BusinessProfile) -> None:
        if str(business.direction or "").strip() not in QUEUE_DIRECTIONS:
            raise ApiError(
                403,
                "queue_direction_forbidden",
                "Bu yo'nalishda navbat tizimi ishlamaydi.",
            )

    async def _enabled_item(
        self,
        session: AsyncSession,
        business_account_id: int,
        public_id: str,
    ) -> CatalogItem:
        item = await self._repository.enabled_item(
            session,
            business_account_id=business_account_id,
            public_id=public_id,
        )
        if item is None:
            raise ApiError(
                400,
                "queue_service_disabled",
                "Bu xizmat uchun navbat yoqilmagan.",
            )
        return item

    async def _provider_context(
        self,
        session: AsyncSession,
        business: BusinessProfile,
        item: CatalogItem,
        provider_id: int,
    ) -> QueueProvider:
        provider = await self._repository.provider(
            session,
            provider_id=provider_id,
            business_account_id=business.account_id,
        )
        linked = (
            provider is not None
            and await self._repository.provider_linked_to_item(
                session,
                provider_id=provider.id,
                catalog_item_id=item.id,
            )
        )
        if provider is None or provider.status != "active" or not linked:
            raise ApiError(
                400,
                "queue_provider_not_assigned",
                "Xizmat ko'rsatuvchi hali biriktirilmagan.",
            )
        if await self._staff_source_exists(session, business):
            active_staff_ids = {
                int(row["id"]) for row in await self._staff_rows(session, business)
            }
            if provider.legacy_staff_id not in active_staff_ids:
                raise ApiError(
                    400,
                    "queue_provider_not_assigned",
                    "Xizmat ko'rsatuvchi hali biriktirilmagan.",
                )
        return provider

    async def _provider_items(
        self,
        session: AsyncSession,
        business_account_id: int,
        body: QueueProviderWrite,
    ) -> list[CatalogItem]:
        items = await self._repository.enabled_items_by_public_ids(
            session,
            business_account_id=business_account_id,
            public_ids=body.item_public_ids,
        )
        by_public = {self._item_public_id(item): item for item in items}
        if len(by_public) != len(body.item_public_ids) or any(
            public_id not in by_public for public_id in body.item_public_ids
        ):
            raise ApiError(
                400,
                "queue_enabled_service_required",
                "Navbat yoqilgan xizmatni tanlang.",
            )
        return [by_public[public_id] for public_id in body.item_public_ids]

    def _provider_times(self, body: QueueProviderWrite) -> tuple[time, time]:
        work_start = _clock(body.work_start)
        work_end = _clock(body.work_end)
        if work_start >= work_end:
            raise ApiError(
                400,
                "queue_provider_hours_invalid",
                "Ish vaqti noto'g'ri.",
            )
        return work_start, work_end

    async def _staff_rows(
        self,
        session: AsyncSession,
        business: BusinessProfile,
    ) -> list[dict[str, object]]:
        rows = await self._staff_repository.members(
            session,
            business.account_id,
            active_only=True,
        )
        return [
            {"id": row.id, "name": row.name, "profession": row.profession}
            for row in rows
        ]

    async def _active_staff(
        self,
        session: AsyncSession,
        business: BusinessProfile,
        staff_id: int,
    ) -> dict[str, object]:
        staff = next(
            (
                row
                for row in await self._staff_rows(session, business)
                if int(row["id"]) == staff_id
            ),
            None,
        )
        if staff is None:
            raise ApiError(400, "queue_active_staff_required", "Faol xodimni tanlang.")
        return staff

    async def _staff_source_exists(
        self,
        session: AsyncSession,
        business: BusinessProfile,
    ) -> bool:
        return bool(
            await self._staff_repository.members(
                session,
                business.account_id,
            )
        )

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

    async def _project(
        self,
        session: AsyncSession,
        queue_id: int,
    ) -> QueueEntryRead:
        row = await self._repository.projected_entry(session, queue_id)
        if row is None:
            raise ApiError(404, "queue_not_found", "Navbat topilmadi.")
        return self._entry_read(*row)

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

    async def _notify(
        self,
        session: AsyncSession,
        entry: QueueEntry,
        *,
        event: str,
        title: str,
        body: str,
        action_type: str,
    ) -> None:
        if entry.customer_account_id is None:
            return
        await self._notifications.append(
            session,
            account_id=entry.customer_account_id,
            account_type="user",
            row={
                "event_key": f"medical_queue:{entry.id}:{event}",
                "title": title,
                "body": body,
                "action_type": action_type,
                "requires_action": 0,
                "is_read": 0,
                "created_at": int(self._now().timestamp()),
                "medical_queue_id": entry.id,
            },
        )

    def _works_on(self, provider: QueueProvider, queue_date: date) -> bool:
        days = {
            part.strip()
            for part in str(provider.work_days or "").split(",")
            if part.strip()
        }
        return not days or str(queue_date.isoweekday()) in days

    def _validate_date(self, queue_date: date) -> None:
        if queue_date < self._local_now().date():
            raise ApiError(
                400,
                "queue_date_in_past",
                "O'tgan sanaga navbat olib bo'lmaydi.",
            )

    def _now(self) -> datetime:
        value = self._now_provider()
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    def _local_now(self) -> datetime:
        return self._now().astimezone(UZBEKISTAN_TZ)

    @staticmethod
    def _item_public_id(item: CatalogItem) -> str:
        return item.public_id or build_content_public_id(item.kind, item.id)
