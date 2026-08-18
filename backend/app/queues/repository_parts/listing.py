"""Ro'yxatlar: biznes navbati va mening navbatlarim."""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.queues.model import (
    QueueEntry,
)
from app.queues.repository_parts.base import QueueRepositoryBase


class ListingMixin(QueueRepositoryBase):
    async def projected_entry(
        self,
        session: AsyncSession,
        queue_id: int,
    ):
        return (
            await session.execute(self._projection().where(QueueEntry.id == queue_id))
        ).first()

    async def list_business(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        queue_date: date,
    ) -> list:
        return list(
            (
                await session.execute(
                    self._projection()
                    .where(
                        QueueEntry.business_account_id == business_account_id,
                        QueueEntry.queue_date == queue_date,
                    )
                    .order_by(
                        QueueEntry.provider_id,
                        QueueEntry.catalog_item_id,
                        QueueEntry.queue_no,
                        QueueEntry.id,
                    )
                )
            ).all()
        )

    async def list_mine(
        self,
        session: AsyncSession,
        *,
        customer_account_id: int,
    ) -> list:
        return list(
            (
                await session.execute(
                    self._projection()
                    .where(QueueEntry.customer_account_id == customer_account_id)
                    .order_by(
                        QueueEntry.queue_date.desc(),
                        QueueEntry.created_at.desc(),
                        QueueEntry.id.desc(),
                    )
                    .limit(200)
                )
            ).all()
        )
