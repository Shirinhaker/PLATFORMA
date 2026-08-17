"""Resurs amallari dispetcheri."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.business_online.payload.actions import apply_action as apply_payload_action
from app.business_online.payload.actions import refresh_derived
from app.business_online.payload.constants import RESOURCE_SPECS
from app.business_online.payload.helpers import (
    find_resource_record,
    missing_record_id,
    sanitize_mapping,
    unix_now,
)
from app.business_online.payload.service import locked_profile
from app.business_online.payload.spec import (
    display_resource_rows,
    ensure_resource_direction,
    resource_rows,
    resource_spec,
)
from app.business_online.service_parts.base import BusinessOnlineServiceBase
from app.cabinet_records.dual_write import sync_json_fallback
from app.core.errors import ApiError
from app.education.repository import (
    ENROLLMENTS as EDUCATION_ENROLLMENTS,
)
from app.education.repository import (
    STUDENTS as EDUCATION_STUDENTS,
)
from app.profiles.model import BusinessProfile


class ActionsMixin(BusinessOnlineServiceBase):
    async def apply_action(
        self,
        account_id: int,
        resource: str,
        action: str,
        *,
        record_id: int | str | None,
        data: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        resource_spec(resource)
        clean = sanitize_mapping(data, allow_id=False)

        async with self._session_factory() as session:
            if (
                resource == "notifications"
                and action in {"mark_read", "mark_all_read"}
                and self._notifications.supported(session)
            ):
                profile = await session.get(BusinessProfile, account_id)
                if profile is None:
                    raise ApiError(
                        404,
                        "business_profile_not_found",
                        "Biznes profil topilmadi.",
                    )
                ensure_resource_direction(profile, resource)
                now = unix_now()
                if action == "mark_all_read":
                    await self._notifications.mark_all_read(
                        session,
                        account_id=account_id,
                        account_type="business",
                        read_at=now,
                    )
                    item = None
                else:
                    if record_id is None:
                        raise missing_record_id()
                    rows = (
                        await self._notifications.list_rows(
                            session,
                            account_id=account_id,
                            account_type="business",
                        )
                        or []
                    )
                    find_resource_record(rows, record_id, resource)
                    try:
                        notification_id = int(record_id)
                    except (TypeError, ValueError):
                        raise ApiError(
                            404,
                            "business_online_record_not_found",
                            "Yozuv topilmadi.",
                        ) from None
                    await self._notifications.mark_read(
                        session,
                        account_id=account_id,
                        account_type="business",
                        notification_id=notification_id,
                        read_at=now,
                    )
                    item = None
                rows = (
                    await self._notifications.list_rows(
                        session,
                        account_id=account_id,
                        account_type="business",
                    )
                    or []
                )
                if record_id is not None:
                    item = find_resource_record(rows, record_id, resource)
                await session.commit()
                return deepcopy(item), deepcopy(rows)
            if (
                resource == EDUCATION_STUDENTS
                and action == "transfer"
                and self._education.supported(session)
            ):
                return await self._education_write(
                    session,
                    account_id=account_id,
                    resource=resource,
                    operation="transfer",
                    record_id=record_id,
                    data=clean,
                )
            if (
                resource == EDUCATION_ENROLLMENTS
                and action in {"accept", "reject"}
                and self._education.supported(session)
            ):
                return await self._apply_enrollment_action(
                    session,
                    account_id=account_id,
                    resource=resource,
                    action=action,
                    record_id=record_id,
                    data=clean,
                )
            profile = await locked_profile(session, account_id)
            ensure_resource_direction(profile, resource)
            payload = await self._hybrid_payload(session, profile)
            before = {
                name: deepcopy(resource_rows(payload, name)) for name in RESOURCE_SPECS
            }
            notification_events: list[dict[str, Any]] = []
            item = apply_payload_action(
                payload,
                resource,
                action,
                record_id=record_id,
                data=clean,
                actor_name=str(profile.name or "").strip() or "Rahbar",
                direction=str(profile.direction or "").strip(),
                notification_events=notification_events,
            )
            changed = {
                name
                for name in RESOURCE_SPECS
                if resource_rows(payload, name) != before[name]
            }
            if not changed:
                changed.add(resource)
            if "notifications" in changed and self._notifications.supported(session):
                await self._persist_business_notifications(
                    session,
                    account_id=account_id,
                    previous=before["notifications"],
                    current=resource_rows(payload, "notifications"),
                )
                payload["notifications"] = deepcopy(before["notifications"])
                changed.discard("notifications")
            catalog_changed = await self._persist_resources(
                session,
                account_id,
                str(profile.name or ""),
                payload,
                changed,
            )
            await self._persist_user_notifications(session, notification_events)
            sync_json_fallback(profile, payload)
            refresh_derived(profile, payload)
            await session.commit()
            await self._invalidate_catalog_cache(catalog_changed)
            return deepcopy(item), display_resource_rows(payload, resource)
