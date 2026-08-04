from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from copy import deepcopy
from typing import Any
from uuid import uuid4

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
    missing_record_id,
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
from app.catalog.cache_epoch import CatalogCacheEpoch
from app.catalog.live_sync import CATALOG_RESOURCES, sync_business_catalog
from app.core.errors import ApiError
from app.education.repository import (
    ENROLLMENTS as EDUCATION_ENROLLMENTS,
    GROUPS as EDUCATION_GROUPS,
    STUDENTS as EDUCATION_STUDENTS,
    EducationEnrollmentRepository,
)
from app.education.service import EducationEnrollmentService
from app.listings.live_sync import LISTING_RESOURCES, sync_business_listings
from app.notifications.repository import NotificationRepository
from app.profiles.model import BusinessProfile, UserProfile


SessionFactory = Callable[[], AsyncIterator[AsyncSession]]
CatalogSync = Callable[..., Awaitable[None]]
ListingSync = Callable[..., Awaitable[None]]
# Ta'lim domenidan o'z jadvaliga ko'chirilgan resurslar.
RELATIONAL_EDUCATION_RESOURCES = (
    EDUCATION_GROUPS,
    EDUCATION_STUDENTS,
    EDUCATION_ENROLLMENTS,
)


class BusinessOnlineService:
    """Relational primary store with temporary synchronized JSON fallback."""

    def __init__(
        self,
        session_factory: SessionFactory,
        repository: CabinetRecordRepository | None = None,
        *,
        catalog_sync: CatalogSync = sync_business_catalog,
        listing_sync: ListingSync = sync_business_listings,
        catalog_cache_epoch: CatalogCacheEpoch | None = None,
        notification_repository: NotificationRepository | None = None,
        education_repository: EducationEnrollmentRepository | None = None,
        education_service: EducationEnrollmentService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or CabinetRecordRepository()
        self._catalog_sync = catalog_sync
        self._listing_sync = listing_sync
        self._catalog_cache_epoch = catalog_cache_epoch
        self._notifications = notification_repository or NotificationRepository()
        self._education = education_repository or EducationEnrollmentRepository()
        self._education_service = education_service or EducationEnrollmentService(
            session_factory,
            repository=self._education,
        )

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
            if resource == "notifications" and self._notifications.supported(session):
                profile = await session.get(BusinessProfile, account_id)
                if profile is None:
                    raise ApiError(
                        404,
                        "business_profile_not_found",
                        "Biznes profil topilmadi.",
                    )
                ensure_resource_direction(profile, resource)
                rows = await self._notifications.list_rows(
                    session,
                    account_id=account_id,
                    account_type="business",
                ) or []
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
                return [
                    row for row in rows
                    if str(row.get("id")) != str(record_id)
                ]
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
                    rows = await self._notifications.list_rows(
                        session,
                        account_id=account_id,
                        account_type="business",
                    ) or []
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
                rows = await self._notifications.list_rows(
                    session,
                    account_id=account_id,
                    account_type="business",
                ) or []
                if record_id is not None:
                    item = find_resource_record(rows, record_id, resource)
                await session.commit()
                return deepcopy(item), deepcopy(rows)
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
            if (
                "notifications" in changed
                and self._notifications.supported(session)
            ):
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

        existing = {
            identity(row)
            for row in previous
            if isinstance(row, dict)
        }
        for row in current:
            if not isinstance(row, dict) or identity(row) in existing:
                continue
            saved = deepcopy(row)
            if not str(saved.get("event_key") or "").strip():
                saved["event_key"] = (
                    f"business:{account_id}:{uuid4().hex}"
                )
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

    async def _apply_enrollment_action(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        resource: str,
        action: str,
        record_id: int | str | None,
        data: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """Ariza qabul qilish/rad etish — uch yozuv bitta tranzaksiyada."""
        profile = await session.get(BusinessProfile, account_id)
        if profile is None:
            raise ApiError(
                404,
                "business_profile_not_found",
                "Biznes profil topilmadi.",
            )
        ensure_resource_direction(profile, resource)
        if record_id is None:
            raise missing_record_id()
        try:
            enrollment_id = int(record_id)
        except (TypeError, ValueError):
            raise ApiError(
                404,
                "new_education_enrollment_not_found",
                "Yangi ariza topilmadi.",
            ) from None
        now = unix_now()
        if action == "accept":
            try:
                group_id = int(data.get("group_id") or 0)
            except (TypeError, ValueError):
                group_id = 0
            await self._education_service.accept_in_session(
                session,
                business_account_id=account_id,
                enrollment_id=enrollment_id,
                group_id=group_id,
                now=now,
            )
        else:
            await self._education_service.reject_in_session(
                session,
                business_account_id=account_id,
                enrollment_id=enrollment_id,
                now=now,
            )
        payload = await self._hybrid_payload(session, profile)
        displayed = display_resource_rows(payload, resource)
        item = next(
            (row for row in displayed if str(row.get("id")) == str(record_id)),
            None,
        )
        await session.commit()
        return deepcopy(item), deepcopy(displayed)

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
        # Ta'lim resurslari o'z jadvallariga ko'chirilgan — ular JSON
        # nusxasidan emas, jadvaldan o'qiladi.
        if self._education.supported(session):
            for resource in RELATIONAL_EDUCATION_RESOURCES:
                rows = await self._education.list_rows(
                    session,
                    business_account_id=profile.account_id,
                    resource=resource,
                )
                if rows is not None:
                    payload[resource] = rows
        return payload

    async def _persist_resources(
        self,
        session: AsyncSession,
        account_id: int,
        owner_name: str,
        payload: dict[str, Any],
        resources: set[str],
    ) -> bool:
        for resource in sorted(resources):
            await self._repository.replace_resource(
                session,
                account_id=account_id,
                account_type="business",
                resource=resource,
                rows=resource_rows(payload, resource),
            )
        catalog_changed = bool(CATALOG_RESOURCES.intersection(resources))
        if catalog_changed:
            await self._catalog_sync(
                session,
                account_id=account_id,
                owner_name=owner_name,
                payload=payload,
                changed_resources=resources,
            )
        listings_changed = bool(LISTING_RESOURCES.intersection(resources))
        if listings_changed:
            await self._listing_sync(
                session,
                account_id=account_id,
                payload=payload,
                changed_resources=resources,
            )
        return catalog_changed or listings_changed

    async def _invalidate_catalog_cache(self, changed: bool) -> None:
        if changed and self._catalog_cache_epoch is not None:
            await self._catalog_cache_epoch.bump()
