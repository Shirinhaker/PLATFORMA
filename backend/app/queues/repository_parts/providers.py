"""Provayderlar va ularning xizmat bog'lanishlari."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.model import CatalogItem
from app.queues.model import (
    QueueEntry,
    QueueProvider,
    QueueProviderService,
)
from app.queues.repository_parts.base import QueueRepositoryBase


class ProvidersMixin(QueueRepositoryBase):
    async def provider(
        self,
        session: AsyncSession,
        *,
        provider_id: int,
        business_account_id: int | None = None,
        lock: bool = False,
    ) -> QueueProvider | None:
        statement = select(QueueProvider).where(QueueProvider.id == provider_id)
        if business_account_id is not None:
            statement = statement.where(
                QueueProvider.business_account_id == business_account_id
            )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def provider_by_staff(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        staff_id: int,
    ) -> QueueProvider | None:
        return await session.scalar(
            select(QueueProvider).where(
                QueueProvider.business_account_id == business_account_id,
                QueueProvider.legacy_staff_id == staff_id,
            )
        )

    async def providers(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
    ) -> list[QueueProvider]:
        return list(
            (
                await session.scalars(
                    select(QueueProvider)
                    .where(QueueProvider.business_account_id == business_account_id)
                    .order_by(
                        QueueProvider.status,
                        func.lower(QueueProvider.staff_name_snapshot),
                        QueueProvider.id,
                    )
                )
            ).all()
        )

    async def provider_links(
        self,
        session: AsyncSession,
        provider_ids: list[int],
    ) -> dict[int, list[CatalogItem]]:
        if not provider_ids:
            return {}
        rows = (
            await session.execute(
                select(QueueProviderService.provider_id, CatalogItem)
                .join(
                    CatalogItem,
                    CatalogItem.id == QueueProviderService.catalog_item_id,
                )
                .where(
                    QueueProviderService.provider_id.in_(provider_ids),
                    QueueProviderService.active.is_(True),
                )
                .order_by(QueueProviderService.provider_id, CatalogItem.id)
            )
        ).all()
        result: dict[int, list[CatalogItem]] = {}
        for provider_id, item in rows:
            result.setdefault(int(provider_id), []).append(item)
        return result

    async def provider_options(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        catalog_item_id: int,
        queue_date: date,
    ) -> list[tuple[QueueProvider, int]]:
        return list(
            (
                await session.execute(
                    select(
                        QueueProvider, func.count(QueueEntry.id).label("queue_count")
                    )
                    .join(
                        QueueProviderService,
                        QueueProviderService.provider_id == QueueProvider.id,
                    )
                    .outerjoin(
                        QueueEntry,
                        (QueueEntry.provider_id == QueueProvider.id)
                        & (QueueEntry.catalog_item_id == catalog_item_id)
                        & (QueueEntry.queue_date == queue_date)
                        & (QueueEntry.status.not_in(("cancelled", "done"))),
                    )
                    .where(
                        QueueProvider.business_account_id == business_account_id,
                        QueueProvider.status == "active",
                        QueueProviderService.catalog_item_id == catalog_item_id,
                        QueueProviderService.active.is_(True),
                    )
                    .group_by(QueueProvider.id)
                    .order_by(
                        func.count(QueueEntry.id),
                        func.lower(QueueProvider.staff_name_snapshot),
                    )
                )
            ).all()
        )

    async def replace_provider_links(
        self,
        session: AsyncSession,
        *,
        provider: QueueProvider,
        items: list[CatalogItem],
        now: datetime,
    ) -> None:
        await session.execute(
            delete(QueueProviderService).where(
                QueueProviderService.provider_id == provider.id
            )
        )
        await session.flush()
        for item in items:
            session.add(
                QueueProviderService(
                    provider_id=provider.id,
                    catalog_item_id=item.id,
                    active=True,
                    duration_minutes=provider.avg_minutes,
                    created_at=now,
                    updated_at=now,
                )
            )
        await session.flush()

    async def provider_linked_to_item(
        self,
        session: AsyncSession,
        *,
        provider_id: int,
        catalog_item_id: int,
    ) -> bool:
        link_id = await session.scalar(
            select(QueueProviderService.id)
            .where(
                QueueProviderService.provider_id == provider_id,
                QueueProviderService.catalog_item_id == catalog_item_id,
                QueueProviderService.active.is_(True),
            )
            .limit(1)
        )
        return link_id is not None
