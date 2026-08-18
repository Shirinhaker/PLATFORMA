"""Umumiy izlash: biznes, foydalanuvchi, xizmat va javob shakli."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.catalog.model import CatalogItem
from app.profiles.model import BusinessProfile, UserProfile
from app.queues.model import (
    QueueEntry,
    QueueProvider,
)
from app.queues.repository_parts.helpers import (
    ACTIVE_STATUSES,
)


class QueueRepositoryBase:
    async def business_by_public_id(
        self,
        session: AsyncSession,
        public_id: str,
    ) -> BusinessProfile | None:
        return await session.scalar(
            select(BusinessProfile)
            .where(BusinessProfile.public_id == public_id)
            .limit(1)
        )

    async def business(
        self,
        session: AsyncSession,
        account_id: int,
    ) -> BusinessProfile | None:
        return await session.get(BusinessProfile, account_id)

    async def user(
        self,
        session: AsyncSession,
        account_id: int,
    ) -> UserProfile | None:
        return await session.get(UserProfile, account_id)

    async def enabled_item(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        public_id: str,
    ) -> CatalogItem | None:
        return await session.scalar(
            select(CatalogItem)
            .where(
                CatalogItem.public_id == public_id,
                CatalogItem.business_account_id == business_account_id,
                CatalogItem.kind == "service",
                CatalogItem.queue_enabled.is_(True),
                CatalogItem.status == "active",
            )
            .limit(1)
        )

    async def enabled_items(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
    ) -> list[CatalogItem]:
        return list(
            (
                await session.scalars(
                    select(CatalogItem)
                    .where(
                        CatalogItem.business_account_id == business_account_id,
                        CatalogItem.kind == "service",
                        CatalogItem.queue_enabled.is_(True),
                        CatalogItem.status == "active",
                    )
                    .order_by(func.lower(CatalogItem.name), CatalogItem.id)
                )
            ).all()
        )

    async def enabled_items_by_public_ids(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        public_ids: list[str],
    ) -> list[CatalogItem]:
        if not public_ids:
            return []
        return list(
            (
                await session.scalars(
                    select(CatalogItem).where(
                        CatalogItem.business_account_id == business_account_id,
                        CatalogItem.public_id.in_(public_ids),
                        CatalogItem.kind == "service",
                        CatalogItem.queue_enabled.is_(True),
                        CatalogItem.status == "active",
                    )
                )
            ).all()
        )

    def _projection(self):
        ahead = aliased(QueueEntry)
        ahead_count = (
            select(func.count(ahead.id))
            .where(
                ahead.provider_id == QueueEntry.provider_id,
                ahead.catalog_item_id == QueueEntry.catalog_item_id,
                ahead.queue_date == QueueEntry.queue_date,
                ahead.queue_no < QueueEntry.queue_no,
                ahead.status.in_(ACTIVE_STATUSES),
            )
            .correlate(QueueEntry)
            .scalar_subquery()
        )
        return (
            select(
                QueueEntry,
                QueueProvider.avg_minutes,
                ahead_count.label("ahead_count"),
                BusinessProfile.name.label("business_name"),
                BusinessProfile.direction.label("business_direction"),
            )
            .join(QueueProvider, QueueProvider.id == QueueEntry.provider_id)
            .join(
                BusinessProfile,
                BusinessProfile.account_id == QueueEntry.business_account_id,
            )
        )
