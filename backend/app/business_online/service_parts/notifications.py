"""Kabinet amallaridan keyingi bildirishnomalar."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.business_online.payload.helpers import normalized_payload
from app.business_online.payload.medical_queue import append_medical_user_notification
from app.business_online.payload.spec import resource_rows
from app.business_online.service_parts.base import BusinessOnlineServiceBase
from app.cabinet_records.dual_write import sync_json_fallback
from app.profiles.model import UserProfile


class NotificationsMixin(BusinessOnlineServiceBase):
    async def _persist_business_notifications(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        previous: list[dict[str, Any]],
        current: list[dict[str, Any]],
    ) -> None:
        def identity(row: dict[str, Any]) -> str:
            event_key = str(row.get("event_key") or "").strip()
            if event_key:
                return f"event:{event_key}"
            return f"id:{row.get('id')}"

        existing = {identity(row) for row in previous if isinstance(row, dict)}
        for row in current:
            if not isinstance(row, dict) or identity(row) in existing:
                continue
            saved = deepcopy(row)
            if not str(saved.get("event_key") or "").strip():
                saved["event_key"] = f"business:{account_id}:{uuid4().hex}"
            await self._notifications.append(
                session,
                account_id=account_id,
                account_type="business",
                row=saved,
            )

    async def _persist_user_notifications(
        self,
        session: AsyncSession,
        events: list[dict[str, Any]],
    ) -> None:
        by_user: dict[int, list[dict[str, Any]]] = {}
        for event in events:
            try:
                user_id = int(event.get("user_id") or 0)
            except (TypeError, ValueError):
                continue
            if user_id:
                by_user.setdefault(user_id, []).append(event)

        if self._notifications.supported(session):
            for user_id, user_events in by_user.items():
                profile = await session.get(UserProfile, user_id)
                if profile is None:
                    continue
                for event in user_events:
                    notification_payload: dict[str, Any] = {"notifications": []}
                    append_medical_user_notification(notification_payload, event)
                    rows = resource_rows(notification_payload, "notifications")
                    if not rows:
                        continue
                    await self._notifications.append(
                        session,
                        account_id=user_id,
                        account_type="user",
                        row=rows[0],
                    )
            return

        for user_id, user_events in by_user.items():
            profile = await session.get(UserProfile, user_id)
            if profile is None:
                continue
            payload = normalized_payload(profile.cabinet_payload)
            payload.update(
                await self._repository.read_payload(
                    session,
                    account_id=user_id,
                    account_type="user",
                )
            )
            for event in user_events:
                append_medical_user_notification(payload, event)
            notifications = resource_rows(payload, "notifications")
            await self._repository.replace_resource(
                session,
                account_id=user_id,
                account_type="user",
                resource="notifications",
                rows=notifications,
            )
            sync_json_fallback(profile, payload)
            snapshot = deepcopy(profile.dashboard_snapshot or {})
            snapshot["unread"] = sum(
                not bool(int(row.get("is_read") or 0)) for row in notifications
            )
            profile.dashboard_snapshot = snapshot
