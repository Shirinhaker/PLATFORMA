"""Umumiy asos: jadval mavjudligi va push navbatiga yozish."""

from __future__ import annotations

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.model import (
    PushDevice,
    PushOutbox,
)
from app.profiles.model import ProfileLink


class NotificationRepositoryBase:
    @staticmethod
    def supported(session: AsyncSession) -> bool:
        return all(hasattr(session, name) for name in ("execute", "scalars", "scalar"))

    async def _enqueue_push(
        self,
        session: AsyncSession,
        *,
        notification_id: int,
        account_id: int,
        account_type: str,
        is_order: bool,
        created_at: int,
    ) -> None:
        preference = await self.preference(
            session,
            account_id=account_id,
            account_type=account_type,
        )
        if preference is not None and (
            not preference.enabled or (is_order and not preference.orders_enabled)
        ):
            return
        device_account_id = account_id
        if account_type == "business":
            linked = await session.scalar(
                select(ProfileLink.user_account_id).where(
                    ProfileLink.business_account_id == account_id
                )
            )
            if linked is not None:
                device_account_id = int(linked)
        device_ids = list(
            (
                await session.scalars(
                    select(PushDevice.id).where(
                        PushDevice.account_id == device_account_id,
                        PushDevice.enabled.is_(True),
                    )
                )
            ).all()
        )
        for device_id in device_ids:
            dialect_name = session.get_bind().dialect.name
            if dialect_name == "postgresql":
                statement = postgresql_insert(PushOutbox)
            elif dialect_name == "sqlite":
                statement = sqlite_insert(PushOutbox)
            else:
                statement = insert(PushOutbox)
            statement = statement.values(
                notification_id=notification_id,
                device_id=int(device_id),
                status="pending",
                attempts=0,
                last_error="",
                created_at=created_at,
                available_at=created_at,
            )
            if hasattr(statement, "on_conflict_do_nothing"):
                statement = statement.on_conflict_do_nothing(
                    index_elements=(
                        PushOutbox.notification_id,
                        PushOutbox.device_id,
                    )
                )
            await session.execute(statement)
