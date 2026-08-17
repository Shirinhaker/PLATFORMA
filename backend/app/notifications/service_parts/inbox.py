"""Kiruvchi qutisi: royxat va oqilgan deb belgilash."""

from __future__ import annotations

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.notifications.schemas import (
    ActionNotificationListRead,
    NotificationListRead,
    NotificationMutationRead,
)
from app.notifications.service_parts.base import NotificationServiceBase


class InboxMixin(NotificationServiceBase):
    async def list(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        staff_id: int | None = None,
        permissions: tuple[str, ...] = (),
    ) -> NotificationListRead:
        async with self._session_factory() as session:
            rows = (
                await self._repository.list_rows(
                    session,
                    account_id=account_id,
                    account_type=account_type.value,
                )
                or []
            )
            visible = [
                row
                for row in rows
                if self._visible(row, staff_id=staff_id, permissions=permissions)
            ]
            unread = sum(
                1
                for row in visible
                if not int(row.get("is_read") or 0)
                and not int(row.get("resolved_at") or 0)
            )
            return NotificationListRead(
                items=[self._read(row) for row in visible],
                unread=unread,
            )

    async def actions(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        staff_id: int | None = None,
        permissions: tuple[str, ...] = (),
    ) -> ActionNotificationListRead:
        async with self._session_factory() as session:
            rows = await self._repository.actionable_rows(
                session,
                account_id=account_id,
                account_type=account_type.value,
            )
            visible = [
                row
                for row in rows
                if self._visible(row, staff_id=staff_id, permissions=permissions)
            ]
            return ActionNotificationListRead(
                items=[self._read(row) for row in visible],
                count=len(visible),
            )

    async def mark_read(
        self,
        *,
        notification_id: int,
        account_id: int,
        account_type: AccountType,
        staff_id: int | None = None,
        permissions: tuple[str, ...] = (),
    ) -> NotificationMutationRead:
        async with self._session_factory() as session:
            row = await self._repository.get_row(
                session,
                account_id=account_id,
                account_type=account_type.value,
                notification_id=notification_id,
            )
            if row is None or not self._visible(
                row, staff_id=staff_id, permissions=permissions
            ):
                raise ApiError(
                    404,
                    "notification_not_found",
                    "Bildirishnoma topilmadi.",
                )
            now = self._now()
            await self._repository.mark_read(
                session,
                account_id=account_id,
                account_type=account_type.value,
                notification_id=notification_id,
                read_at=now,
                resolve=str(row.get("action_type") or "") == "view_ready",
            )
            await session.commit()
            return NotificationMutationRead(read_at=now)

    async def mark_all_read(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        staff_id: int | None = None,
        permissions: tuple[str, ...] = (),
    ) -> NotificationMutationRead:
        async with self._session_factory() as session:
            now = self._now()
            if staff_id is None:
                await self._repository.mark_all_read(
                    session,
                    account_id=account_id,
                    account_type=account_type.value,
                    read_at=now,
                )
            else:
                rows = (
                    await self._repository.list_rows(
                        session,
                        account_id=account_id,
                        account_type=account_type.value,
                    )
                    or []
                )
                ids = [
                    int(row["id"])
                    for row in rows
                    if not int(row.get("is_read") or 0)
                    and self._visible(row, staff_id=staff_id, permissions=permissions)
                ]
                await self._repository.mark_ids_read(
                    session,
                    account_id=account_id,
                    account_type=account_type.value,
                    notification_ids=ids,
                    read_at=now,
                )
            await session.commit()
            return NotificationMutationRead(read_at=now)
