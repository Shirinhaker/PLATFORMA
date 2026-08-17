"""Kabinet yozuvlari: oqish, yaratish, tahrirlash, ochirish."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.business_online.payload_service import (
    EDUCATION_RESOURCES,
    IMMUTABLE_FIELDS,
    MEDICAL_RESOURCES,
    cascade_after_delete,
    display_resource_rows,
    ensure_resource_direction,
    find_resource_record,
    find_resource_record_index,
    locked_profile,
    next_record_id,
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
from app.business_online.service_parts.base import BusinessOnlineServiceBase
from app.business_online.service_parts.helpers import (
    RELATIONAL_EDUCATION_WRITES,
)
from app.cabinet_records.dual_write import sync_json_fallback
from app.core.errors import ApiError
from app.profiles.model import BusinessProfile


class CrudMixin(BusinessOnlineServiceBase):
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
            if resource == "notifications" and self._notifications.supported(session):
                rows = await self._notifications.list_rows(
                    session,
                    account_id=account_id,
                    account_type="business",
                )
                return rows or []
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
            if resource in RELATIONAL_EDUCATION_WRITES and self._education.supported(
                session
            ):
                return await self._education_write(
                    session,
                    account_id=account_id,
                    resource=resource,
                    operation="create",
                    record_id=None,
                    data=clean,
                )
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
            catalog_changed = await self._persist_resources(
                session,
                account_id,
                str(profile.name or ""),
                payload,
                changed,
            )
            sync_json_fallback(profile, payload)
            refresh_derived(profile, payload)
            await session.commit()
            await self._invalidate_catalog_cache(catalog_changed)
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
            if resource in RELATIONAL_EDUCATION_WRITES and self._education.supported(
                session
            ):
                return await self._education_write(
                    session,
                    account_id=account_id,
                    resource=resource,
                    operation="update",
                    record_id=record_id,
                    data=clean,
                )
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
            catalog_changed = await self._persist_resources(
                session,
                account_id,
                str(profile.name or ""),
                payload,
                changed,
            )
            sync_json_fallback(profile, payload)
            refresh_derived(profile, payload)
            await session.commit()
            await self._invalidate_catalog_cache(catalog_changed)
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
            if resource in RELATIONAL_EDUCATION_WRITES and self._education.supported(
                session
            ):
                _item, rows = await self._education_write(
                    session,
                    account_id=account_id,
                    resource=resource,
                    operation="delete",
                    record_id=record_id,
                    data={},
                )
                return rows
            if resource == "notifications" and self._notifications.supported(session):
                profile = await session.get(BusinessProfile, account_id)
                if profile is None:
                    raise ApiError(
                        404,
                        "business_profile_not_found",
                        "Biznes profil topilmadi.",
                    )
                ensure_resource_direction(profile, resource)
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
                await self._notifications.delete(
                    session,
                    account_id=account_id,
                    account_type="business",
                    notification_id=notification_id,
                )
                await session.commit()
                return [row for row in rows if str(row.get("id")) != str(record_id)]
            profile = await locked_profile(session, account_id)
            ensure_resource_direction(profile, resource)
            payload = await self._hybrid_payload(session, profile)
            rows = resource_rows(payload, resource)
            deleted = rows.pop(
                find_resource_record_index(
                    rows,
                    record_id,
                    resource,
                )
            )
            payload[resource] = rows
            changed = cascade_after_delete(payload, resource, deleted)
            catalog_changed = await self._persist_resources(
                session,
                account_id,
                str(profile.name or ""),
                payload,
                changed,
            )
            sync_json_fallback(profile, payload)
            refresh_derived(profile, payload)
            await session.commit()
            await self._invalidate_catalog_cache(catalog_changed)
            return deepcopy(rows)
