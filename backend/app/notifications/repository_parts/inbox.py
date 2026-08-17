"""Kiruvchi quti: yozish, o'qish, belgilash, o'chirish."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.model import (
    Notification,
)
from app.notifications.repository_parts.base import NotificationRepositoryBase
from app.notifications.repository_parts.helpers import (
    PAYLOAD_COMPAT_COLUMNS,
    ROW_COLUMNS,
    _boolean,
    _integer,
    _row,
)


class InboxMixin(NotificationRepositoryBase):
    async def append(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        row: Mapping[str, object],
    ) -> None:
        event_key = str(row.get("event_key") or "").strip()
        if not event_key:
            raise ValueError("notification_event_key_required")
        created_at = _integer(
            row.get("created_at"),
            int(datetime.now(UTC).timestamp()),
        )
        values = {
            "account_id": account_id,
            "account_type": account_type,
            "event_key": event_key[:200],
            "title": str(row.get("title") or "")[:300],
            "body": str(row.get("body") or ""),
            "order_id": _integer(row.get("order_id")) or None,
            "listing_id": _integer(row.get("listing_id")) or None,
            "dining_order_id": _integer(row.get("dining_order_id")) or None,
            "medical_queue_id": _integer(row.get("medical_queue_id")) or None,
            "ride_id": _integer(row.get("ride_id")) or None,
            "target_staff_id": _integer(row.get("target_staff_id")) or None,
            "target_permission": str(
                row.get("target_permission") or row.get("target_perm") or ""
            )[:80],
            "action_type": str(row.get("action_type") or "")[:80],
            "requires_action": _boolean(row.get("requires_action")),
            "is_read": _boolean(row.get("is_read")),
            "created_at": created_at,
            "read_at": _integer(row.get("read_at")) or None,
            "resolved_at": _integer(row.get("resolved_at")) or None,
            "payload": {
                **{
                    str(key): value
                    for key, value in row.items()
                    if str(key) not in ROW_COLUMNS
                },
                **{
                    key: row[key]
                    for key in PAYLOAD_COMPAT_COLUMNS
                    if key in row and row[key] is not None
                },
            },
        }
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(Notification)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(Notification)
        else:
            statement = insert(Notification)
        statement = statement.values(**values)
        if hasattr(statement, "on_conflict_do_nothing"):
            statement = statement.on_conflict_do_nothing(
                index_elements=(
                    Notification.account_id,
                    Notification.account_type,
                    Notification.event_key,
                )
            )
        await session.execute(statement)
        notification_id = await session.scalar(
            select(Notification.id).where(
                Notification.account_id == account_id,
                Notification.account_type == account_type,
                Notification.event_key == event_key[:200],
            )
        )
        if notification_id is not None:
            await self._enqueue_push(
                session,
                notification_id=int(notification_id),
                account_id=account_id,
                account_type=account_type,
                is_order=values["order_id"] is not None,
                created_at=created_at,
            )

    async def list_rows(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
    ) -> list[dict[str, Any]] | None:
        if not self.supported(session):
            return None
        notifications = list(
            (
                await session.scalars(
                    select(Notification)
                    .where(
                        Notification.account_id == account_id,
                        Notification.account_type == account_type,
                    )
                    .order_by(Notification.created_at, Notification.id)
                    .limit(200)
                )
            ).all()
        )
        return [_row(notification) for notification in notifications]

    async def get_row(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        notification_id: int,
    ) -> dict[str, Any] | None:
        notification = await session.scalar(
            select(Notification)
            .where(
                Notification.id == notification_id,
                Notification.account_id == account_id,
                Notification.account_type == account_type,
            )
            .limit(1)
        )
        return _row(notification) if notification is not None else None

    async def unread_count(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
    ) -> int:
        count = await session.scalar(
            select(func.count(Notification.id)).where(
                Notification.account_id == account_id,
                Notification.account_type == account_type,
                Notification.is_read.is_(False),
            )
        )
        return int(count or 0)

    async def actionable_rows(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        notifications = list(
            (
                await session.scalars(
                    select(Notification)
                    .where(
                        Notification.account_id == account_id,
                        Notification.account_type == account_type,
                        Notification.requires_action.is_(True),
                        Notification.is_read.is_(False),
                        Notification.resolved_at.is_(None),
                    )
                    .order_by(Notification.created_at, Notification.id)
                    .limit(limit)
                )
            ).all()
        )
        return [_row(notification) for notification in notifications]

    async def mark_order_read(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        order_id: int,
        read_at: int,
    ) -> None:
        await session.execute(
            update(Notification)
            .where(
                Notification.account_id == account_id,
                Notification.account_type == account_type,
                Notification.order_id == order_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True, read_at=read_at)
        )

    async def mark_read(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        notification_id: int,
        read_at: int,
        resolve: bool = False,
    ) -> None:
        values: dict[str, object] = {"is_read": True, "read_at": read_at}
        if resolve:
            values["resolved_at"] = read_at
        await session.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.account_id == account_id,
                Notification.account_type == account_type,
            )
            .values(**values)
        )

    async def mark_all_read(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        read_at: int,
    ) -> None:
        await session.execute(
            update(Notification)
            .where(
                Notification.account_id == account_id,
                Notification.account_type == account_type,
                Notification.is_read.is_(False),
            )
            .values(is_read=True, read_at=read_at)
        )

    async def mark_ids_read(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        notification_ids: list[int],
        read_at: int,
    ) -> None:
        if not notification_ids:
            return
        await session.execute(
            update(Notification)
            .where(
                Notification.account_id == account_id,
                Notification.account_type == account_type,
                Notification.id.in_(notification_ids),
                Notification.is_read.is_(False),
            )
            .values(is_read=True, read_at=read_at)
        )

    async def delete(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        notification_id: int,
    ) -> None:
        await session.execute(
            delete(Notification).where(
                Notification.id == notification_id,
                Notification.account_id == account_id,
                Notification.account_type == account_type,
            )
        )
