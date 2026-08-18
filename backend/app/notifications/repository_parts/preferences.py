"""Sozlamalar va kategoriya filtrlari."""

from __future__ import annotations

from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.model import (
    NotificationFilter,
    NotificationPreference,
)
from app.notifications.repository_parts.base import NotificationRepositoryBase


class PreferencesMixin(NotificationRepositoryBase):
    async def preference(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
    ) -> NotificationPreference | None:
        return await session.scalar(
            select(NotificationPreference).where(
                NotificationPreference.account_id == account_id,
                NotificationPreference.account_type == account_type,
            )
        )

    async def save_preference(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        enabled: bool,
        orders_enabled: bool,
        updated_at: int,
    ) -> None:
        values = {
            "account_id": account_id,
            "account_type": account_type,
            "enabled": enabled,
            "orders_enabled": orders_enabled,
            "updated_at": updated_at,
        }
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(NotificationPreference)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(NotificationPreference)
        else:
            statement = insert(NotificationPreference)
        statement = statement.values(**values)
        if hasattr(statement, "on_conflict_do_update"):
            statement = statement.on_conflict_do_update(
                index_elements=(
                    NotificationPreference.account_id,
                    NotificationPreference.account_type,
                ),
                set_={
                    "enabled": enabled,
                    "orders_enabled": orders_enabled,
                    "updated_at": updated_at,
                },
            )
        await session.execute(statement)

    async def filters(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
    ) -> list[NotificationFilter]:
        return list(
            (
                await session.scalars(
                    select(NotificationFilter)
                    .where(
                        NotificationFilter.account_id == account_id,
                        NotificationFilter.account_type == account_type,
                    )
                    .order_by(NotificationFilter.id.desc())
                )
            ).all()
        )

    async def filters_for_category(
        self,
        session: AsyncSession,
        *,
        category: str,
    ) -> list[NotificationFilter]:
        return list(
            (
                await session.scalars(
                    select(NotificationFilter)
                    .where(NotificationFilter.category == category)
                    .order_by(NotificationFilter.id)
                )
            ).all()
        )

    async def add_filter(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        category: str,
        region: str,
        district: str,
        price_min: int,
        price_max: int,
        keyword: str,
        created_at: int,
    ) -> NotificationFilter:
        row = NotificationFilter(
            account_id=account_id,
            account_type=account_type,
            category=category,
            region=region,
            district=district,
            price_min=price_min,
            price_max=price_max,
            keyword=keyword,
            created_at=created_at,
        )
        session.add(row)
        await session.flush()
        return row

    async def remove_filter(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        filter_id: int,
    ) -> int:
        result = await session.execute(
            delete(NotificationFilter).where(
                NotificationFilter.id == filter_id,
                NotificationFilter.account_id == account_id,
                NotificationFilter.account_type == account_type,
            )
        )
        return int(result.rowcount or 0)
