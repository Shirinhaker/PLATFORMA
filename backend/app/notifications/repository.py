from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.model import (
    Notification,
    NotificationFilter,
    NotificationPreference,
    PushDevice,
    PushOutbox,
)
from app.profiles.model import ProfileLink


ROW_COLUMNS = frozenset({
    "id",
    "event_key",
    "title",
    "body",
    "order_id",
    "listing_id",
    "dining_order_id",
    "medical_queue_id",
    "ride_id",
    "target_staff_id",
    "target_permission",
    "action_type",
    "requires_action",
    "is_read",
    "created_at",
    "read_at",
    "resolved_at",
})
PAYLOAD_COMPAT_COLUMNS = (
    "order_id",
    "listing_id",
    "dining_order_id",
    "medical_queue_id",
    "ride_id",
    "target_staff_id",
    "target_permission",
)


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
        "listing_id": notification.listing_id,
        "dining_order_id": notification.dining_order_id,
        "medical_queue_id": notification.medical_queue_id,
        "ride_id": notification.ride_id,
        "target_staff_id": notification.target_staff_id,
        "target_permission": notification.target_permission,
        "action_type": notification.action_type,
        "requires_action": 1 if notification.requires_action else 0,
        "is_read": 1 if notification.is_read else 0,
        "created_at": notification.created_at,
    })
    if notification.read_at is not None:
        result["read_at"] = notification.read_at
    else:
        result.pop("read_at", None)
    if notification.resolved_at is not None:
        result["resolved_at"] = notification.resolved_at
    else:
        result.pop("resolved_at", None)
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
        before_id: int | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]] | None:
        if not self.supported(session):
            return None
        statement = (
            select(Notification).where(
                Notification.account_id == account_id,
                Notification.account_type == account_type,
            )
        )
        if before_id is not None:
            statement = statement.where(Notification.id < before_id)
        notifications = list((await session.scalars(
            statement
            .order_by(Notification.id.desc())
            .limit(limit + 1)
        )).all())
        # The database reads newest-first so the LIMIT always keeps the newest
        # rows.  Keep the public/repository contract chronological for UI
        # rendering and compatibility with cabinet projections.
        notifications.reverse()
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

    async def unread_rows(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
    ) -> list[dict[str, Any]]:
        notifications = list((await session.scalars(
            select(Notification).where(
                Notification.account_id == account_id,
                Notification.account_type == account_type,
                Notification.is_read.is_(False),
            )
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

    async def actionable_rows(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        notifications = list((await session.scalars(
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
        )).all())
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
        return list((await session.scalars(
            select(NotificationFilter)
            .where(
                NotificationFilter.account_id == account_id,
                NotificationFilter.account_type == account_type,
            )
            .order_by(NotificationFilter.id.desc())
        )).all())

    async def filters_for_category(
        self,
        session: AsyncSession,
        *,
        category: str,
    ) -> list[NotificationFilter]:
        return list((await session.scalars(
            select(NotificationFilter)
            .where(NotificationFilter.category == category)
            .order_by(NotificationFilter.id)
        )).all())

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
        device_ids = list((await session.scalars(
            select(PushDevice.id).where(
                PushDevice.account_id == device_account_id,
                PushDevice.enabled.is_(True),
            )
        )).all())
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
