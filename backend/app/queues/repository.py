from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.catalog.model import CatalogItem
from app.profiles.model import BusinessProfile, UserProfile
from app.queues.model import (
    QueueCounter,
    QueueEntry,
    QueueHistory,
    QueueProvider,
    QueueProviderService,
)


ACTIVE_STATUSES = ("waiting", "called", "in_service")


def active_provider_count(catalog_item_id, business_account_id):
    return (
        select(func.count(QueueProviderService.id))
        .select_from(QueueProviderService)
        .join(
            QueueProvider,
            QueueProvider.id == QueueProviderService.provider_id,
        )
        .where(
            QueueProviderService.catalog_item_id == catalog_item_id,
            QueueProviderService.active.is_(True),
            QueueProvider.business_account_id == business_account_id,
            QueueProvider.status == "active",
        )
        .correlate(CatalogItem)
        .scalar_subquery()
    )


class QueueRepository:
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
        return list((await session.scalars(
            select(CatalogItem)
            .where(
                CatalogItem.business_account_id == business_account_id,
                CatalogItem.kind == "service",
                CatalogItem.queue_enabled.is_(True),
                CatalogItem.status == "active",
            )
            .order_by(func.lower(CatalogItem.name), CatalogItem.id)
        )).all())

    async def enabled_items_by_public_ids(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        public_ids: list[str],
    ) -> list[CatalogItem]:
        if not public_ids:
            return []
        return list((await session.scalars(
            select(CatalogItem).where(
                CatalogItem.business_account_id == business_account_id,
                CatalogItem.public_id.in_(public_ids),
                CatalogItem.kind == "service",
                CatalogItem.queue_enabled.is_(True),
                CatalogItem.status == "active",
            )
        )).all())

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
        return list((await session.scalars(
            select(QueueProvider)
            .where(QueueProvider.business_account_id == business_account_id)
            .order_by(
                QueueProvider.status,
                func.lower(QueueProvider.staff_name_snapshot),
                QueueProvider.id,
            )
        )).all())

    async def provider_links(
        self,
        session: AsyncSession,
        provider_ids: list[int],
    ) -> dict[int, list[CatalogItem]]:
        if not provider_ids:
            return {}
        rows = (await session.execute(
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
        )).all()
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
        return list((await session.execute(
            select(QueueProvider, func.count(QueueEntry.id).label("queue_count"))
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
            .order_by(func.count(QueueEntry.id), func.lower(QueueProvider.staff_name_snapshot))
        )).all())

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
            session.add(QueueProviderService(
                provider_id=provider.id,
                catalog_item_id=item.id,
                active=True,
                duration_minutes=provider.avg_minutes,
                created_at=now,
                updated_at=now,
            ))
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
        return await session.scalar(
            select(QueueEntry.id).where(*conditions).limit(1)
        ) is not None

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
        return await session.scalar(
            select(QueueEntry.id)
            .where(
                QueueEntry.business_account_id == business_account_id,
                QueueEntry.catalog_item_id == catalog_item_id,
                QueueEntry.provider_id == provider_id,
                QueueEntry.queue_date == queue_date,
                QueueEntry.slot_time == slot_time,
            )
            .limit(1)
        ) is not None

    async def taken_slots(
        self,
        session: AsyncSession,
        *,
        catalog_item_id: int,
        provider_id: int,
        queue_date: date,
    ) -> set:
        values = (await session.scalars(
            select(QueueEntry.slot_time).where(
                QueueEntry.catalog_item_id == catalog_item_id,
                QueueEntry.provider_id == provider_id,
                QueueEntry.queue_date == queue_date,
                QueueEntry.slot_time.is_not(None),
                QueueEntry.status.in_(("waiting", "called", "in_service", "done")),
            )
        )).all()
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
            statement = statement.values(**values).on_conflict_do_update(
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
            ).returning(QueueCounter.last_number)
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
        return list((await session.scalars(
            select(QueueEntry)
            .where(
                QueueEntry.business_account_id == business_account_id,
                QueueEntry.id.in_(sorted(queue_ids)),
            )
            .order_by(QueueEntry.id)
            .with_for_update()
        )).all())

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
            )
            .join(QueueProvider, QueueProvider.id == QueueEntry.provider_id)
        )

    async def projected_entry(
        self,
        session: AsyncSession,
        queue_id: int,
    ):
        return (await session.execute(
            self._projection().where(QueueEntry.id == queue_id)
        )).first()

    async def list_business(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        queue_date: date,
    ) -> list:
        return list((await session.execute(
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
        )).all())

    async def list_mine(
        self,
        session: AsyncSession,
        *,
        customer_account_id: int,
    ) -> list:
        return list((await session.execute(
            self._projection()
            .where(QueueEntry.customer_account_id == customer_account_id)
            .order_by(
                QueueEntry.queue_date.desc(),
                QueueEntry.created_at.desc(),
                QueueEntry.id.desc(),
            )
            .limit(200)
        )).all())

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
        session.add(QueueHistory(
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
        ))
        await session.flush()
