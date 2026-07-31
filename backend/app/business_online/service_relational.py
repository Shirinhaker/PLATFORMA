from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from copy import deepcopy
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.business_online.service import (
    EDUCATION_RESOURCES,
    IMMUTABLE_FIELDS,
    MEDICAL_RESOURCES,
    RESOURCE_SPECS,
    append_medical_user_notification,
    apply_action as apply_payload_action,
    cascade_after_delete,
    display_resource_rows,
    ensure_resource_direction,
    find_resource_record,
    find_resource_record_index,
    locked_profile,
    next_record_id,
    normalized_payload,
    operation_forbidden,
    prepare_patch_for_resource,
    prepare_record_for_create,
    refresh_derived,
    resource_rows,
    resource_spec,
    sanitize_mapping,
    sync_dining_place_activity,
    sync_medical_doctor_links,
    unix_now,
)
from app.cabinet_records.dual_write import sync_json_fallback
from app.cabinet_records.repository import CabinetRecordRepository
from app.core.errors import ApiError
from app.profiles.model import BusinessProfile, UserProfile


SessionFactory = Callable[[], AsyncIterator[AsyncSession]]


class BusinessOnlineService:
    """Relational primary store with temporary synchronized JSON fallback."""

    def __init__(
        self,
        session_factory: SessionFactory,
        repository: CabinetRecordRepository | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or CabinetRecordRepository()

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
            if (
                resource == "dining_places"
                or resource in MEDICAL_RESOURCES
                or resource in EDUCATION_RESOURCES
            ):
                payload = await self._hybrid_payload(session, profile)
                sync_dining_place_activity(payload)
                return display_resource_rows(payload, resource)
            rows = await self._resource_rows(
                session,
                profile=profile,
                account_id=account_id,
                resource=resource,
            )
            return [row for row in rows if isinstance(row, dict)]

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
            payload = await self._hybrid_payload(session, profile)
            rows = resource_rows(payload, resource)
            prepare_record_for_create(resource, clean, rows, payload=payload)
            now = unix_now()
            clean["id"] = next_record_id(rows)
            clean.setdefault("created_at", now)
            clean["updated_at"] = now
            rows.append(clean)
            payload[resource] = rows
            changed = {resource}
            if resource == "medical_doctors":
                sync_medical_doctor_links(payload, clean, account_id)
                changed.add("medical_doctor_services")
            await self._persist_resources(session, account_id, payload, changed)
            sync_json_fallback(profile, payload)
            refresh_derived(profile, payload)
            await session.commit()
            displayed = display_resource_rows(payload, resource)
            item = next(
                row for row in displayed if str(row.get("id")) == str(clean["id"])
            )
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
            payload = await self._hybrid_payload(session, profile)
            rows = resource_rows(payload, resource)
            item = find_resource_record(rows, record_id, resource)
            prepare_patch_for_resource(resource, item, clean, payload=payload)
            item.update(clean)
            item["updated_at"] = unix_now()
            payload[resource] = rows
            changed = {resource}
            if resource == "medical_doctors":
                sync_medical_doctor_links(payload, item, account_id)
                changed.add("medical_doctor_services")
            await self._persist_resources(session, account_id, payload, changed)
            sync_json_fallback(profile, payload)
            refresh_derived(profile, payload)
            await session.commit()
            displayed = display_resource_rows(payload, resource)
            saved = next(
                row for row in displayed if str(row.get("id")) == str(record_id)
            )
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
            payload = await self._hybrid_payload(session, profile)
            rows = resource_rows(payload, resource)
            deleted = rows.pop(find_resource_record_index(
                rows,
                record_id,
                resource,
            ))
            payload[resource] = rows
            changed = cascade_after_delete(payload, resource, deleted)
            await self._persist_resources(session, account_id, payload, changed)
            sync_json_fallback(profile, payload)
            refresh_derived(profile, payload)
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
            payload = await self._hybrid_payload(session, profile)
            before = {
                name: deepcopy(resource_rows(payload, name))
                for name in RESOURCE_SPECS
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
            await self._persist_resources(session, account_id, payload, changed)
            await self._persist_user_notifications(session, notification_events)
            sync_json_fallback(profile, payload)
            refresh_derived(profile, payload)
            await session.commit()
            return deepcopy(item), display_resource_rows(payload, resource)

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

        for user_id, user_events in by_user.items():
            profile = await session.get(UserProfile, user_id)
            if profile is None:
                continue
            payload = normalized_payload(profile.cabinet_payload)
            payload.update(await self._repository.read_payload(
                session,
                account_id=user_id,
                account_type="user",
            ))
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
                not bool(int(row.get("is_read") or 0))
                for row in notifications
            )
            profile.dashboard_snapshot = snapshot

    async def _resource_rows(
        self,
        session: AsyncSession,
        *,
        profile: BusinessProfile,
        account_id: int,
        resource: str,
    ) -> list[Any]:
        if await self._repository.has_resource(
            session,
            account_id=account_id,
            account_type="business",
            resource=resource,
        ):
            return await self._repository.read_resource(
                session,
                account_id=account_id,
                account_type="business",
                resource=resource,
            )
        return resource_rows(profile.cabinet_payload, resource)

    async def _hybrid_payload(
        self,
        session: AsyncSession,
        profile: BusinessProfile,
    ) -> dict[str, Any]:
        payload = normalized_payload(profile.cabinet_payload)
        relational = await self._repository.read_payload(
            session,
            account_id=profile.account_id,
            account_type="business",
        )
        payload.update(relational)
        return payload

    async def _persist_resources(
        self,
        session: AsyncSession,
        account_id: int,
        payload: dict[str, Any],
        resources: set[str],
    ) -> None:
        for resource in sorted(resources):
            await self._repository.replace_resource(
                session,
                account_id=account_id,
                account_type="business",
                resource=resource,
                rows=resource_rows(payload, resource),
            )
