"""Kabinet payloadining JSON yo'li — `BusinessOnlinePayloadService`.

Bu **zaxira yo'l**: hali relatsion jadvalga ko'chirilmagan bo'limlar
shu orqali ishlaydi. Yangi funksiya `business_online/service.py` ga
yoziladi.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.business_online.payload.actions import (
    apply_action,
    refresh_derived,
)
from app.business_online.payload.constants import (
    IMMUTABLE_FIELDS,
    SessionFactory,
)
from app.business_online.payload.dining import (
    sync_dining_place_activity,
)
from app.business_online.payload.helpers import (
    find_record,
    find_resource_record,
    find_resource_record_index,
    integer,
    next_record_id,
    normalized_payload,
    raw_payload_rows,
    sanitize_mapping,
    unix_now,
)
from app.business_online.payload.medical import (
    sync_medical_doctor_links,
)
from app.business_online.payload.medical_queue import (
    append_medical_user_notification,
)
from app.business_online.payload.spec import (
    cascade_after_delete,
    display_resource_rows,
    ensure_resource_direction,
    operation_forbidden,
    prepare_patch_for_resource,
    prepare_record_for_create,
    resource_rows,
    resource_spec,
)
from app.core.errors import ApiError
from app.profiles.model import BusinessProfile, UserProfile


class BusinessOnlinePayloadService:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def read_resource(
        self,
        account_id: int,
        resource: str,
    ) -> list[dict[str, Any]]:
        resource_spec(resource)
        async with self._session_factory() as session:
            profile = await session.get(BusinessProfile, account_id)
            if profile is None:
                raise ApiError(
                    404,
                    "business_profile_not_found",
                    "Biznes profil topilmadi.",
                )
            ensure_resource_direction(profile, resource)
            payload = normalized_payload(profile.cabinet_payload)
            sync_dining_place_activity(payload)
            return display_resource_rows(payload, resource)

    async def create_record(
        self,
        account_id: int,
        resource: str,
        record: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        spec = resource_spec(resource)
        if not spec.create:
            raise operation_forbidden(resource)
        clean = sanitize_mapping(record, allow_id=False)
        if not clean:
            raise ApiError(422, "empty_record", "Yozuv ma’lumotlari bo‘sh.")

        async with self._session_factory() as session:
            profile = await locked_profile(session, account_id)
            ensure_resource_direction(profile, resource)
            payload = normalized_payload(profile.cabinet_payload)
            rows = resource_rows(payload, resource)
            prepare_record_for_create(resource, clean, rows, payload=payload)
            now = unix_now()
            clean["id"] = next_record_id(rows)
            clean.setdefault("created_at", now)
            clean["updated_at"] = now
            rows.append(clean)
            payload[resource] = rows
            if resource == "medical_doctors":
                sync_medical_doctor_links(payload, clean, account_id)
            refresh_derived(profile, payload)
            profile.cabinet_payload = payload
            await session.commit()
            displayed = display_resource_rows(payload, resource)
            item = find_record(displayed, clean["id"])
            return deepcopy(item), deepcopy(displayed)

    async def patch_record(
        self,
        account_id: int,
        resource: str,
        record_id: int | str,
        patch: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        spec = resource_spec(resource)
        if not spec.update:
            raise operation_forbidden(resource)
        clean = sanitize_mapping(patch, allow_id=False)
        for key in IMMUTABLE_FIELDS:
            clean.pop(key, None)
        if not clean:
            raise ApiError(422, "empty_patch", "O‘zgartirish ma’lumotlari bo‘sh.")

        async with self._session_factory() as session:
            profile = await locked_profile(session, account_id)
            ensure_resource_direction(profile, resource)
            payload = normalized_payload(profile.cabinet_payload)
            rows = resource_rows(payload, resource)
            item = find_resource_record(rows, record_id, resource)
            prepare_patch_for_resource(resource, item, clean, payload=payload)
            item.update(clean)
            item["updated_at"] = unix_now()
            payload[resource] = rows
            if resource == "medical_doctors":
                sync_medical_doctor_links(payload, item, account_id)
            refresh_derived(profile, payload)
            profile.cabinet_payload = payload
            await session.commit()
            displayed = display_resource_rows(payload, resource)
            saved = find_record(displayed, record_id)
            return deepcopy(saved), deepcopy(displayed)

    async def delete_record(
        self,
        account_id: int,
        resource: str,
        record_id: int | str,
    ) -> list[dict[str, Any]]:
        spec = resource_spec(resource)
        if not spec.delete:
            raise operation_forbidden(resource)

        async with self._session_factory() as session:
            profile = await locked_profile(session, account_id)
            ensure_resource_direction(profile, resource)
            payload = normalized_payload(profile.cabinet_payload)
            rows = resource_rows(payload, resource)
            index = find_resource_record_index(rows, record_id, resource)
            deleted = rows.pop(index)
            payload[resource] = rows
            cascade_after_delete(payload, resource, deleted)
            refresh_derived(profile, payload)
            profile.cabinet_payload = payload
            await session.commit()
            return deepcopy(rows)

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
            profile = await locked_profile(session, account_id)
            ensure_resource_direction(profile, resource)
            payload = normalized_payload(profile.cabinet_payload)
            notification_events: list[dict[str, Any]] = []
            item = apply_action(
                payload,
                resource,
                action,
                record_id=record_id,
                data=clean,
                actor_name=str(profile.name or "").strip() or "Rahbar",
                direction=str(profile.direction or "").strip(),
                notification_events=notification_events,
            )
            await persist_user_notifications(session, notification_events)
            refresh_derived(profile, payload)
            profile.cabinet_payload = payload
            await session.commit()
            return deepcopy(item), display_resource_rows(payload, resource)


async def locked_profile(session: AsyncSession, account_id: int) -> BusinessProfile:
    profile = await session.scalar(
        select(BusinessProfile)
        .where(BusinessProfile.account_id == account_id)
        .with_for_update()
    )
    if profile is None:
        raise ApiError(404, "business_profile_not_found", "Biznes profil topilmadi.")
    return profile


async def persist_user_notifications(
    session: AsyncSession,
    events: list[dict[str, Any]],
) -> None:
    for event in events:
        user_id = integer(event.get("user_id"))
        if not user_id:
            continue
        profile = await session.get(UserProfile, user_id)
        if profile is None:
            continue
        payload = normalized_payload(profile.cabinet_payload)
        append_medical_user_notification(payload, event)
        notifications = raw_payload_rows(payload, "notifications")
        snapshot = deepcopy(profile.dashboard_snapshot or {})
        snapshot["unread"] = sum(
            not bool(integer(row.get("is_read"))) for row in notifications
        )
        profile.dashboard_snapshot = snapshot
        profile.cabinet_payload = payload
