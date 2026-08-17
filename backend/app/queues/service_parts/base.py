"""Umumiy asos: bog'liqliklar, kontekst yuklash, javob shakli."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.model import CatalogItem
from app.core.errors import ApiError
from app.notifications.repository_parts import NotificationRepository
from app.profiles.model import BusinessProfile
from app.queues.model import QueueEntry, QueueProvider
from app.queues.repository_parts import QueueRepository
from app.queues.service_parts.helpers import (
    QUEUE_DIRECTIONS,
    UZBEKISTAN_TZ,
    NowProvider,
    SessionFactory,
)
from app.queues.service_parts.projection import QueueProjectionMixin
from app.staff.repository import StaffRepository


class QueueServiceBase(QueueProjectionMixin):
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
