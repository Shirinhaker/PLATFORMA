"""Navbat yozuvlari: band vaqtlar, raqam berish, tarix."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.queues.model import (
    QueueCounter,
    QueueEntry,
    QueueHistory,
)
from app.queues.repository_parts.base import QueueRepositoryBase
from app.queues.repository_parts.helpers import (
    ACTIVE_STATUSES,
)


class EntriesMixin(QueueRepositoryBase):
    async def active_customer_duplicate(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        catalog_item_id: int,
        provider_id: int,
        queue_date: date,
        customer_account_id: int,
        slot_time,
    ) -> bool:
        conditions = [
            QueueEntry.business_account_id == business_account_id,
            QueueEntry.catalog_item_id == catalog_item_id,
            QueueEntry.provider_id == provider_id,
            QueueEntry.queue_date == queue_date,
            QueueEntry.customer_account_id == customer_account_id,
            QueueEntry.status.in_(ACTIVE_STATUSES),
        ]
        if slot_time is None:
            conditions.append(QueueEntry.slot_time.is_(None))
        else:
            conditions.append(QueueEntry.slot_time == slot_time)
        return (
            await session.scalar(select(QueueEntry.id).where(*conditions).limit(1))
            is not None
        )

    async def slot_taken(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        catalog_item_id: int,
        provider_id: int,
        queue_date: date,
        slot_time,
    ) -> bool:
        return (
            await session.scalar(
                select(QueueEntry.id)
                .where(
                    QueueEntry.business_account_id == business_account_id,
                    QueueEntry.catalog_item_id == catalog_item_id,
                    QueueEntry.provider_id == provider_id,
                    QueueEntry.queue_date == queue_date,
                    QueueEntry.slot_time == slot_time,
                )
                .limit(1)
            )
            is not None
        )

    async def taken_slots(
        self,
        session: AsyncSession,
        *,
        catalog_item_id: int,
        provider_id: int,
        queue_date: date,
    ) -> set:
        values = (
            await session.scalars(
                select(QueueEntry.slot_time).where(
                    QueueEntry.catalog_item_id == catalog_item_id,
                    QueueEntry.provider_id == provider_id,
                    QueueEntry.queue_date == queue_date,
                    QueueEntry.slot_time.is_not(None),
                    QueueEntry.status.in_(("waiting", "called", "in_service", "done")),
                )
            )
        ).all()
        return {value for value in values if value is not None}

    async def allocate_live_number(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        catalog_item_id: int,
        provider_id: int,
        queue_date: date,
        now: datetime,
    ) -> int:
        values = {
            "business_account_id": business_account_id,
            "catalog_item_id": catalog_item_id,
            "provider_id": provider_id,
            "queue_date": queue_date,
            "last_number": 1,
            "updated_at": now,
        }
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(QueueCounter)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(QueueCounter)
        else:
            statement = None
        if statement is not None:
            statement = (
                statement.values(**values)
                .on_conflict_do_update(
                    index_elements=(
                        QueueCounter.business_account_id,
                        QueueCounter.catalog_item_id,
                        QueueCounter.provider_id,
                        QueueCounter.queue_date,
                    ),
                    set_={
                        "last_number": QueueCounter.last_number + 1,
                        "updated_at": now,
                    },
                )
                .returning(QueueCounter.last_number)
            )
            value = await session.scalar(statement)
            return int(value)

        identity = (
            business_account_id,
            catalog_item_id,
            provider_id,
            queue_date,
        )
        counter = await session.get(QueueCounter, identity, with_for_update=True)
        if counter is None:
            counter = QueueCounter(**values)
            session.add(counter)
        else:
            counter.last_number += 1
            counter.updated_at = now
        await session.flush()
        return int(counter.last_number)

    async def add_entry(self, session: AsyncSession, entry: QueueEntry) -> None:
        session.add(entry)
        await session.flush()

    async def entry(
        self,
        session: AsyncSession,
        *,
        queue_id: int,
        business_account_id: int | None = None,
        customer_account_id: int | None = None,
        lock: bool = False,
    ) -> QueueEntry | None:
        statement = select(QueueEntry).where(QueueEntry.id == queue_id)
        if business_account_id is not None:
            statement = statement.where(
                QueueEntry.business_account_id == business_account_id
            )
        if customer_account_id is not None:
            statement = statement.where(
                QueueEntry.customer_account_id == customer_account_id
            )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def entries_for_swap(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        queue_ids: list[int],
    ) -> list[QueueEntry]:
        # Bir xil ID tartibi deadlockning oldini oladi.
        return list(
            (
                await session.scalars(
                    select(QueueEntry)
                    .where(
                        QueueEntry.business_account_id == business_account_id,
                        QueueEntry.id.in_(sorted(queue_ids)),
                    )
                    .order_by(QueueEntry.id)
                    .with_for_update()
                )
            ).all()
        )

    async def next_waiting(
        self,
        session: AsyncSession,
        current: QueueEntry,
    ) -> QueueEntry | None:
        return await session.scalar(
            select(QueueEntry)
            .where(
                QueueEntry.business_account_id == current.business_account_id,
                QueueEntry.catalog_item_id == current.catalog_item_id,
                QueueEntry.provider_id == current.provider_id,
                QueueEntry.queue_date == current.queue_date,
                QueueEntry.status == "waiting",
                QueueEntry.queue_no > current.queue_no,
            )
            .order_by(QueueEntry.queue_no, QueueEntry.id)
            .limit(1)
        )

    async def add_history(
        self,
        session: AsyncSession,
        *,
        entry: QueueEntry,
        action: str,
        old_value: str,
        new_value: str,
        actor_account_id: int | None,
        now: datetime,
    ) -> None:
        session.add(
            QueueHistory(
                business_account_id=entry.business_account_id,
                queue_id=entry.id,
                legacy_source_id=None,
                action=action,
                old_value=old_value[:160],
                new_value=new_value[:160],
                actor_account_id=actor_account_id,
                legacy_actor_staff_id=None,
                note="",
                created_at=now,
            )
        )
        await session.flush()
