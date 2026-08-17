"""Push qurilmalari va ularning holati."""

from __future__ import annotations

from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.model import (
    PushDevice,
    PushOutbox,
)
from app.notifications.repository_parts.base import NotificationRepositoryBase


class DevicesMixin(NotificationRepositoryBase):
    async def register_device(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        token: str,
        platform: str,
        device_name: str,
        app_version: str,
        now: int,
    ) -> int:
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(PushDevice)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(PushDevice)
        else:
            statement = insert(PushDevice)
        statement = statement.values(
            account_id=account_id,
            token=token,
            platform=platform,
            device_name=device_name,
            app_version=app_version,
            enabled=True,
            created_at=now,
            updated_at=now,
            last_seen_at=now,
        )
        if hasattr(statement, "on_conflict_do_update"):
            statement = statement.on_conflict_do_update(
                index_elements=(PushDevice.token,),
                set_={
                    "account_id": account_id,
                    "platform": platform,
                    "device_name": device_name,
                    "app_version": app_version,
                    "enabled": True,
                    "updated_at": now,
                    "last_seen_at": now,
                },
            )
        await session.execute(statement)
        device_id = await session.scalar(
            select(PushDevice.id).where(PushDevice.token == token)
        )
        return int(device_id or 0)

    async def unregister_device(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        token: str,
        now: int,
    ) -> int:
        result = await session.execute(
            update(PushDevice)
            .where(
                PushDevice.account_id == account_id,
                PushDevice.token == token,
            )
            .values(enabled=False, updated_at=now)
        )
        return int(result.rowcount or 0)

    async def push_status(
        self,
        session: AsyncSession,
        *,
        account_id: int,
    ) -> tuple[int, int]:
        active = await session.scalar(
            select(func.count(PushDevice.id)).where(
                PushDevice.account_id == account_id,
                PushDevice.enabled.is_(True),
            )
        )
        pending = await session.scalar(
            select(func.count(PushOutbox.id))
            .join(PushDevice, PushDevice.id == PushOutbox.device_id)
            .where(
                PushDevice.account_id == account_id,
                PushOutbox.status == "pending",
            )
        )
        return int(active or 0), int(pending or 0)
