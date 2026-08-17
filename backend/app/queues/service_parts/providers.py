"""Navbat provayderlari: shifokor/xizmat va ish jadvali."""

from __future__ import annotations

from datetime import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.model import CatalogItem
from app.core.errors import ApiError
from app.profiles.model import BusinessProfile
from app.queues.model import QueueProvider
from app.queues.schemas import (
    QueueBusinessSetupRead,
    QueueProviderRead,
    QueueProviderWrite,
    QueueServiceRead,
    QueueStaffRead,
)
from app.queues.service_parts.base import QueueServiceBase
from app.queues.service_parts.helpers import _clock


class ProvidersMixin(QueueServiceBase):
    async def business_setup(
        self, *, business_account_id: int
    ) -> QueueBusinessSetupRead:
        async with self._session_factory() as session:
            business = await self._business(session, business_account_id)
            services = await self._repository.enabled_items(
                session,
                business_account_id=business_account_id,
            )
            staff = await self._staff_rows(session, business)
            response = QueueBusinessSetupRead(
                services=[
                    QueueServiceRead(
                        public_id=self._item_public_id(item),
                        name=item.name,
                        price_text=item.price_text,
                    )
                    for item in services
                ],
                staff=[
                    QueueStaffRead(
                        id=int(row["id"]),
                        name=str(row["name"]),
                        profession=str(row["profession"]),
                    )
                    for row in staff
                ],
            )
            await session.rollback()
            return response

    async def list_providers(
        self,
        *,
        business_account_id: int,
    ) -> list[QueueProviderRead]:
        async with self._session_factory() as session:
            await self._business(session, business_account_id)
            providers = await self._repository.providers(
                session,
                business_account_id=business_account_id,
            )
            links = await self._repository.provider_links(
                session, [provider.id for provider in providers]
            )
            response = [
                self._provider_read(provider, links.get(provider.id, []))
                for provider in providers
            ]
            await session.rollback()
            return response

    async def create_provider(
        self,
        *,
        business_account_id: int,
        body: QueueProviderWrite,
    ) -> QueueProviderRead:
        async with self._session_factory() as session:
            business = await self._business(session, business_account_id)
            if (
                await self._repository.provider_by_staff(
                    session,
                    business_account_id=business_account_id,
                    staff_id=body.staff_id,
                )
                is not None
            ):
                raise ApiError(
                    409,
                    "queue_provider_exists",
                    "Xizmat ko'rsatuvchi avval biriktirilgan.",
                )
            staff = await self._active_staff(session, business, body.staff_id)
            items = await self._provider_items(session, business_account_id, body)
            work_start, work_end = self._provider_times(body)
            now = self._now()
            provider = QueueProvider(
                business_account_id=business_account_id,
                legacy_source_id=None,
                legacy_staff_id=body.staff_id,
                staff_name_snapshot=str(staff["name"])[:120],
                profession_snapshot=str(staff["profession"])[:120],
                specialty=body.specialty,
                experience_years=body.experience_years,
                qualification=body.qualification,
                work_days=body.work_days,
                work_start=work_start,
                work_end=work_end,
                avg_minutes=body.avg_minutes,
                room=body.room,
                bio=body.bio,
                status=body.status,
                mode=body.mode,
                created_at=now,
                updated_at=now,
            )
            session.add(provider)
            await session.flush()
            await self._repository.replace_provider_links(
                session,
                provider=provider,
                items=items,
                now=now,
            )
            await session.commit()
            return self._provider_read(provider, items)

    async def update_provider(
        self,
        *,
        business_account_id: int,
        provider_id: int,
        body: QueueProviderWrite,
    ) -> QueueProviderRead:
        async with self._session_factory() as session:
            business = await self._business(session, business_account_id)
            provider = await self._repository.provider(
                session,
                provider_id=provider_id,
                business_account_id=business_account_id,
                lock=True,
            )
            if provider is None:
                raise ApiError(
                    404,
                    "queue_provider_not_found",
                    "Xizmat ko'rsatuvchi topilmadi.",
                )
            if body.staff_id != provider.legacy_staff_id:
                raise ApiError(
                    400,
                    "queue_provider_staff_immutable",
                    "Xizmat ko'rsatuvchi xodimini o'zgartirib bo'lmaydi.",
                )
            items = await self._provider_items(session, business_account_id, body)
            work_start, work_end = self._provider_times(body)
            provider.specialty = body.specialty
            provider.experience_years = body.experience_years
            provider.qualification = body.qualification
            provider.work_days = body.work_days
            provider.work_start = work_start
            provider.work_end = work_end
            provider.avg_minutes = body.avg_minutes
            provider.room = body.room
            provider.bio = body.bio
            provider.status = body.status
            provider.mode = body.mode
            provider.updated_at = self._now()
            await self._repository.replace_provider_links(
                session,
                provider=provider,
                items=items,
                now=provider.updated_at,
            )
            await session.commit()
            return self._provider_read(provider, items)

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
