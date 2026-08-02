from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.model import Notification


ROW_COLUMNS = frozenset({
    "id",
    "event_key",
    "title",
    "body",
    "order_id",
    "action_type",
    "requires_action",
    "is_read",
    "created_at",
    "read_at",
})


def _integer(value: object, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _boolean(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


def _row(notification: Notification) -> dict[str, Any]:
    result = dict(notification.payload or {})
    result.update({
        "id": notification.id,
        "event_key": notification.event_key,
        "title": notification.title,
        "body": notification.body,
        "order_id": notification.order_id,
        "action_type": notification.action_type,
        "requires_action": 1 if notification.requires_action else 0,
        "is_read": 1 if notification.is_read else 0,
        "created_at": notification.created_at,
    })
    if notification.read_at is not None:
        result["read_at"] = notification.read_at
    else:
        result.pop("read_at", None)
    return result


class NotificationRepository:
    @staticmethod
    def supported(session: AsyncSession) -> bool:
        return all(
            hasattr(session, name)
            for name in ("execute", "scalars", "scalar")
        )

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
            "action_type": str(row.get("action_type") or "")[:80],
            "requires_action": _boolean(row.get("requires_action")),
            "is_read": _boolean(row.get("is_read")),
            "created_at": created_at,
            "read_at": _integer(row.get("read_at")) or None,
            "payload": {
                str(key): value
                for key, value in row.items()
                if str(key) not in ROW_COLUMNS
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

    async def list_rows(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
    ) -> list[dict[str, Any]] | None:
        if not self.supported(session):
            return None
        notifications = list((await session.scalars(
            select(Notification)
            .where(
                Notification.account_id == account_id,
                Notification.account_type == account_type,
            )
            .order_by(Notification.created_at, Notification.id)
        )).all())
        return [_row(notification) for notification in notifications]

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
    ) -> None:
        await session.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.account_id == account_id,
                Notification.account_type == account_type,
            )
            .values(is_read=True, read_at=read_at)
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
