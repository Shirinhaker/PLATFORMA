from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isfinite
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.profiles.model import BusinessProfile, UserProfile


SessionFactory = Callable[[], AsyncIterator[AsyncSession]]


@dataclass(frozen=True)
class ResourceSpec:
    create: bool = False
    update: bool = False
    delete: bool = False


RESOURCE_SPECS: dict[str, ResourceSpec] = {
    "business_subscriptions": ResourceSpec(),
    "subscription_payments": ResourceSpec(),
    "item_groups": ResourceSpec(create=True, update=True, delete=True),
    "items": ResourceSpec(create=True, update=True, delete=True),
    "listings": ResourceSpec(create=True, update=True, delete=True),
    "orders": ResourceSpec(update=True),
    "messages": ResourceSpec(create=True, update=True, delete=True),
    "business_reviews": ResourceSpec(update=True),
    "advertisements": ResourceSpec(create=True, update=True, delete=True),
    "stories": ResourceSpec(create=True, update=True, delete=True),
    "notifications": ResourceSpec(update=True, delete=True),
    "notify_filters": ResourceSpec(create=True, delete=True),
    "followers": ResourceSpec(),
    "following": ResourceSpec(delete=True),
    "dining_places": ResourceSpec(create=True, update=True, delete=True),
    "dining_orders": ResourceSpec(),
    "medical_staff": ResourceSpec(),
    "medical_doctors": ResourceSpec(create=True, update=True),
    "medical_doctor_services": ResourceSpec(),
    "medical_queue": ResourceSpec(),
    "medical_queue_history": ResourceSpec(),
    "education_groups": ResourceSpec(),
    "education_students": ResourceSpec(),
    "education_enrollments": ResourceSpec(),
}

SENSITIVE_NAMES = {
    "password",
    "password_hash",
    "pass_hash",
    "pass_plain",
    "token",
    "token_hash",
    "secret",
    "private_key",
    "csrf_token",
    "telegram_user_id",
}
SENSITIVE_SUFFIXES = ("_password", "_secret", "_token", "_hash")
OWNERSHIP_FIELDS = {
    "account_id",
    "business_id",
    "user_id",
    "owner_id",
    "owner_account_id",
    "actor_id",
    "actor_account_id",
}
IMMUTABLE_FIELDS = OWNERSHIP_FIELDS | {"id", "created_at"}
ORDER_STATUSES = {
    "new",
    "accepted",
    "payment_waiting",
    "payment_confirmed",
    "preparing",
    "ready",
    "tayyor",
    "courier_search",
    "courier_assigned",
    "courier_arrived_store",
    "handoff_waiting_seller",
    "in_delivery",
    "courier_arrived_customer",
    "delivered_waiting_customer",
    "delivered",
    "pickup_waiting_customer",
    "done",
    "rejected",
    "cancelled",
    "canceled",
}
GENERIC_STATUSES = {
    "draft",
    "pending",
    "active",
    "paused",
    "archived",
    "approved",
    "rejected",
    "expired",
    "cancelled",
    "canceled",
}
TERMINAL_ORDER_STATUSES = {
    "done",
    "delivered",
    "pickup_waiting_customer",
    "rejected",
    "cancelled",
    "canceled",
}
QUEUE_DIRECTIONS = {
    "Transport va logistika",
    "Xizmat ko'rsatish",
    "Maishiy xizmatlar",
    "Qurilish",
    "Tibbiy xizmatlar",
    "Ko'chmas mulk",
    "Axborot texnologiyalari",
    "Konsalting va professional",
    "Madaniyat, sport, ko'ngilochar",
    "Turizm va mehmonxona",
    "Reklama va marketing",
    "Poligrafiya va nashriyot",
    "Moliyaviy faoliyat",
    "Import-eksport",
}
MEDICAL_RESOURCES = {
    "medical_staff",
    "medical_doctors",
    "medical_doctor_services",
    "medical_queue",
    "medical_queue_history",
}
EDUCATION_RESOURCES = {
    "education_groups",
    "education_students",
    "education_enrollments",
}
MEDICAL_QUEUE_STATUSES = {
    "waiting",
    "called",
    "in_service",
    "done",
    "no_show",
    "cancelled",
    "skipped",
}
MEDICAL_QUEUE_TERMINAL = {"done", "cancelled", "no_show"}


class BusinessOnlineService:
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


def resource_spec(resource: str) -> ResourceSpec:
    spec = RESOURCE_SPECS.get(resource)
    if spec is None:
        raise ApiError(
            404,
            "business_online_resource_not_found",
            "Bu onlayn kabinet bo‘limi mavjud emas.",
        )
    return spec


def operation_forbidden(resource: str) -> ApiError:
    return ApiError(
        403,
        "business_online_operation_forbidden",
        f"{resource} bo‘limida bu amal ruxsat etilmagan.",
    )


def ensure_resource_direction(profile: BusinessProfile, resource: str) -> None:
    if (
        resource in {"dining_places", "dining_orders"}
        and str(profile.direction or "").strip() != "Umumiy ovqatlanish"
    ):
        raise ApiError(
            403,
            "dining_direction_required",
            "Bu bo'lim faqat Umumiy ovqatlanish yo'nalishi uchun.",
        )
    if (
        resource in MEDICAL_RESOURCES
        and str(profile.direction or "").strip() not in QUEUE_DIRECTIONS
    ):
        raise ApiError(
            403,
            "queue_direction_required",
            "Bu yo'nalishda navbat tizimi ishlamaydi.",
        )
    if (
        resource in EDUCATION_RESOURCES
        and str(profile.direction or "").strip() != "Ta'lim faoliyati"
    ):
        raise ApiError(
            403,
            "education_direction_required",
            "Bu bo'lim faqat Ta'lim faoliyati yo'nalishi uchun.",
        )


def prepare_record_for_create(
    resource: str,
    clean: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    payload: dict[str, Any] | None = None,
) -> None:
    if resource == "medical_doctors":
        prepare_medical_doctor(payload or {}, clean)
        return
    if resource != "dining_places":
        return
    kind = str(clean.get("kind") or "").strip()
    if kind not in {"table", "room"}:
        raise ApiError(
            400,
            "invalid_dining_place_kind",
            "Stol yoki xona turini tanlang.",
        )
    name = str(clean.get("name") or "").strip()[:60]
    seats = integer_or_default(clean.get("seats"), 0)
    clean.clear()
    clean.update({
        "kind": kind,
        "name": name or ("Stol" if kind == "table" else "Xona"),
        "seats": (
            max(0, min(100, seats))
            if kind == "table"
            else 0
        ),
        "x": 4 + (len(rows) % 5) * 18,
        "y": 4,
        "locked": 1,
    })


def prepare_patch_for_resource(
    resource: str,
    item: dict[str, Any],
    clean: dict[str, Any],
    *,
    payload: dict[str, Any] | None = None,
) -> None:
    if resource == "medical_doctors":
        clean.pop("staff_id", None)
        prepare_medical_doctor(payload or {}, clean, current=item)
        return
    if resource != "dining_places":
        return
    prepared: dict[str, Any] = {}
    if "name" in clean:
        prepared["name"] = str(clean.get("name") or "").strip()[:60] or item["name"]
    if "seats" in clean:
        prepared["seats"] = (
            max(0, min(100, integer_or_default(clean.get("seats"), 0)))
            if item.get("kind") == "table"
            else 0
        )
    try:
        if "x" in clean:
            prepared["x"] = max(0.0, min(90.0, float(clean["x"])))
        if "y" in clean:
            prepared["y"] = max(0.0, min(88.0, float(clean["y"])))
    except (TypeError, ValueError):
        raise ApiError(
            400,
            "invalid_dining_place_position",
            "Joylashuv qiymati noto'g'ri.",
        ) from None
    if "locked" in clean:
        prepared["locked"] = 1 if str(clean["locked"]).lower() in {"1", "true"} else 0
    clean.clear()
    clean.update(prepared)


def cascade_after_delete(
    payload: dict[str, Any],
    resource: str,
    deleted: dict[str, Any],
) -> set[str]:
    changed = {resource}
    if resource == "dining_places":
        place_id = str(deleted.get("id"))
        payload["dining_orders"] = [
            row
            for row in resource_rows(payload, "dining_orders")
            if str(row.get("place_id")) != place_id
        ]
        changed.add("dining_orders")
    return changed


async def locked_profile(session: AsyncSession, account_id: int) -> BusinessProfile:
    profile = await session.scalar(
        select(BusinessProfile)
        .where(BusinessProfile.account_id == account_id)
        .with_for_update()
    )
    if profile is None:
        raise ApiError(404, "business_profile_not_found", "Biznes profil topilmadi.")
    return profile


def normalized_payload(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def resource_rows(payload: Any, resource: str) -> list[dict[str, Any]]:
    resource_spec(resource)
    return raw_payload_rows(payload, resource)


def raw_payload_rows(payload: Any, resource: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    value = payload.get(resource)
    if not isinstance(value, list):
        return []
    return [deepcopy(row) for row in value if isinstance(row, dict)]


def display_resource_rows(
    payload: dict[str, Any],
    resource: str,
) -> list[dict[str, Any]]:
    if resource == "medical_staff":
        return medical_staff_rows(payload)
    if resource == "medical_doctors":
        return medical_doctor_rows(payload)
    if resource == "medical_queue":
        return medical_queue_rows(payload)
    if resource == "education_groups":
        return education_group_rows(payload)
    if resource == "education_enrollments":
        return education_enrollment_rows(payload)
    return resource_rows(payload, resource)


def education_group_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = {
        str(row.get("id")): row
        for row in raw_payload_rows(payload, "items")
    }
    students = raw_payload_rows(payload, "education_students")
    result = []
    for source in raw_payload_rows(payload, "education_groups"):
        if str(source.get("status") or "") != "active":
            continue
        row = deepcopy(source)
        course = items.get(str(row.get("course_item_id")), {})
        row["course_name"] = str(
            row.get("course_name") or course.get("name") or ""
        )
        row["student_count"] = sum(
            str(student.get("group_id")) == str(row.get("id"))
            and str(student.get("status") or "") == "active"
            for student in students
        )
        result.append(row)
    result.sort(key=lambda row: integer(row.get("id")), reverse=True)
    return result


def education_enrollment_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = {
        str(row.get("id")): row
        for row in raw_payload_rows(payload, "items")
    }
    groups = {
        str(row.get("id")): row
        for row in raw_payload_rows(payload, "education_groups")
    }
    result = []
    for source in raw_payload_rows(payload, "education_enrollments"):
        row = deepcopy(source)
        course = items.get(str(row.get("course_item_id")), {})
        group = groups.get(str(row.get("group_id")), {})
        row["course_name"] = str(
            row.get("course_name") or course.get("name") or ""
        )
        row["group_name"] = str(
            row.get("group_name") or group.get("name") or ""
        )
        result.append(row)
    rank = {"new": 0, "accepted": 1}
    result.sort(key=lambda row: (
        rank.get(str(row.get("status") or ""), 2),
        -integer(row.get("id")),
    ))
    return result[:500]


def medical_staff_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    source: list[dict[str, Any]] = []
    for resource in ("staff", "business_staff", "employees"):
        source = raw_payload_rows(payload, resource)
        if source:
            break
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in source:
        identifier = integer(row.get("id"))
        if not identifier or str(identifier) in seen:
            continue
        status = str(row.get("status") or "active")
        if status != "active":
            continue
        seen.add(str(identifier))
        result.append({
            "id": identifier,
            "name": str(row.get("name") or "")[:120],
            "profession": str(row.get("profession") or "Xodim")[:120],
            "status": "active",
        })
    result.sort(key=lambda row: str(row.get("name") or ""))
    return result


def medical_doctor_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    staff = {
        str(row.get("id")): row
        for row in medical_staff_rows(payload)
    }
    links = raw_payload_rows(payload, "medical_doctor_services")
    result = []
    for source in raw_payload_rows(payload, "medical_doctors"):
        row = deepcopy(source)
        staff_row = staff.get(str(row.get("staff_id")), {})
        row["name"] = str(row.get("name") or staff_row.get("name") or "")
        row["profession"] = str(
            row.get("profession") or staff_row.get("profession") or "Xodim"
        )
        linked_ids = [
            integer(link.get("item_id"))
            for link in links
            if str(link.get("staff_id")) == str(row.get("staff_id"))
            and bool(integer_or_default(link.get("active"), 1))
        ]
        inline_ids = normalized_integer_list(row.get("item_ids"))
        row["item_ids"] = linked_ids if linked_ids else inline_ids
        result.append(row)
    result.sort(key=lambda row: (
        str(row.get("status") or ""),
        str(row.get("name") or ""),
    ))
    return result


def medical_queue_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = {
        str(row.get("id")): row
        for row in raw_payload_rows(payload, "items")
    }
    staff = {
        str(row.get("id")): row
        for row in medical_staff_rows(payload)
    }
    result = []
    for source in raw_payload_rows(payload, "medical_queue"):
        row = deepcopy(source)
        item = items.get(str(row.get("item_id")), {})
        provider = staff.get(str(row.get("staff_id")), {})
        row["service_name"] = str(
            row.get("service_name") or item.get("name") or ""
        )
        row["doctor_name"] = str(
            row.get("doctor_name") or provider.get("name") or ""
        )
        result.append(row)
    result.sort(key=lambda row: (
        integer(row.get("staff_id")),
        integer(row.get("item_id")),
        integer(row.get("queue_no")),
    ))
    return result


def normalized_integer_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    result: list[int] = []
    for item in value:
        identifier = integer(item)
        if identifier and identifier not in result:
            result.append(identifier)
    return result


def prepare_medical_doctor(
    payload: dict[str, Any],
    clean: dict[str, Any],
    *,
    current: dict[str, Any] | None = None,
) -> None:
    source = {**(current or {}), **clean}
    staff_id = integer(source.get("staff_id"))
    staff = next(
        (
            row
            for row in medical_staff_rows(payload)
            if integer(row.get("id")) == staff_id
        ),
        None,
    )
    if staff is None:
        raise ApiError(400, "active_medical_staff_required", "Faol xodimni tanlang.")

    item_ids = normalized_integer_list(source.get("item_ids"))
    queue_items = {
        integer(row.get("id"))
        for row in raw_payload_rows(payload, "items")
        if str(row.get("kind") or "") == "service"
        and queue_enabled(row.get("queue_enabled"))
    }
    if not item_ids or any(item_id not in queue_items for item_id in item_ids):
        raise ApiError(
            400,
            "queue_enabled_service_required",
            "Navbat yoqilgan xizmatni tanlang.",
        )

    prepared = {
        "staff_id": staff_id,
        "specialty": str(source.get("specialty") or "").strip()[:100],
        "experience_years": max(0, integer(source.get("experience_years"))),
        "qualification": str(source.get("qualification") or "").strip()[:100],
        "work_days": str(source.get("work_days") or "1,2,3,4,5,6")[:30],
        "work_start": str(source.get("work_start") or "08:00")[:5],
        "work_end": str(source.get("work_end") or "17:00")[:5],
        "avg_minutes": max(5, min(240, integer_or_default(
            source.get("avg_minutes"), 20
        ))),
        "room": str(source.get("room") or "").strip()[:50],
        "bio": str(source.get("bio") or "").strip()[:500],
        "status": "inactive" if source.get("status") == "inactive" else "active",
        "mode": "slot" if source.get("mode") == "slot" else "live",
        "item_ids": item_ids,
        "name": str(staff.get("name") or "")[:120],
        "profession": str(staff.get("profession") or "Xodim")[:120],
    }
    if current is None:
        clean.clear()
        clean.update(prepared)
        return
    clean.clear()
    clean.update({
        key: value
        for key, value in prepared.items()
        if key not in {"staff_id", "name", "profession"}
    })


def sync_medical_doctor_links(
    payload: dict[str, Any],
    doctor: dict[str, Any],
    business_id: int,
) -> None:
    staff_id = integer(doctor.get("staff_id"))
    links = [
        row
        for row in raw_payload_rows(payload, "medical_doctor_services")
        if str(row.get("staff_id")) != str(staff_id)
    ]
    minutes = max(5, min(240, integer_or_default(doctor.get("avg_minutes"), 20)))
    links.extend({
        "business_id": business_id,
        "staff_id": staff_id,
        "item_id": item_id,
        "active": 1,
        "duration_minutes": minutes,
    } for item_id in normalized_integer_list(doctor.get("item_ids")))
    payload["medical_doctor_services"] = links


def queue_enabled(value: Any) -> bool:
    return value is True or str(value).strip().casefold() in {"1", "true", "on"}


def sanitize_mapping(value: dict[str, Any], *, allow_id: bool) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ApiError(422, "invalid_record", "Yozuv obyekt bo‘lishi kerak.")
    if len(value) > 100:
        raise ApiError(422, "record_too_large", "Yozuvda maydonlar juda ko‘p.")
    result: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        lowered = key.casefold()
        if not key or len(key) > 80:
            raise ApiError(422, "invalid_record_key", "Yozuv maydoni noto‘g‘ri.")
        if lowered in SENSITIVE_NAMES or lowered.endswith(SENSITIVE_SUFFIXES):
            raise ApiError(
                422,
                "sensitive_record_field",
                "Maxfiy maydonni kabinet yozuviga saqlash mumkin emas.",
            )
        if lowered in OWNERSHIP_FIELDS or (lowered == "id" and not allow_id):
            continue
        result[key] = sanitize_value(raw_value, depth=0)
    return result


def sanitize_value(value: Any, *, depth: int) -> Any:
    if depth > 5:
        raise ApiError(422, "record_too_deep", "Yozuv tuzilmasi juda chuqur.")
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if isfinite(value) else None
    if isinstance(value, str):
        if len(value) > 20_000:
            raise ApiError(422, "record_value_too_long", "Matn juda uzun.")
        return value
    if isinstance(value, list):
        if len(value) > 500:
            raise ApiError(422, "record_list_too_long", "Ro‘yxat juda uzun.")
        return [sanitize_value(item, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        return {
            str(key): sanitize_value(item, depth=depth + 1)
            for key, item in value.items()
            if str(key).casefold() not in SENSITIVE_NAMES
            and not str(key).casefold().endswith(SENSITIVE_SUFFIXES)
        }
    return str(value)


def next_record_id(rows: list[dict[str, Any]]) -> int:
    identifiers = []
    for row in rows:
        try:
            identifiers.append(int(row.get("id") or 0))
        except (TypeError, ValueError):
            continue
    return max(identifiers, default=0) + 1


def find_record(
    rows: list[dict[str, Any]],
    record_id: int | str,
) -> dict[str, Any]:
    return rows[find_record_index(rows, record_id)]


def find_record_index(
    rows: list[dict[str, Any]],
    record_id: int | str,
) -> int:
    expected = str(record_id)
    for index, row in enumerate(rows):
        if str(row.get("id")) == expected:
            return index
    raise ApiError(404, "business_online_record_not_found", "Yozuv topilmadi.")


def find_resource_record(
    rows: list[dict[str, Any]],
    record_id: int | str,
    resource: str,
) -> dict[str, Any]:
    return rows[find_resource_record_index(rows, record_id, resource)]


def find_resource_record_index(
    rows: list[dict[str, Any]],
    record_id: int | str,
    resource: str,
) -> int:
    try:
        return find_record_index(rows, record_id)
    except ApiError:
        if resource == "dining_places":
            raise ApiError(
                404,
                "dining_place_not_found",
                "Stol yoki xona topilmadi.",
            ) from None
        if resource == "medical_doctors":
            raise ApiError(
                404,
                "medical_provider_not_found",
                "Xizmat ko'rsatuvchi topilmadi.",
            ) from None
        if resource == "medical_queue":
            raise ApiError(
                404,
                "medical_queue_not_found",
                "Navbat topilmadi.",
            ) from None
        raise


def apply_action(
    payload: dict[str, Any],
    resource: str,
    action: str,
    *,
    record_id: int | str | None,
    data: dict[str, Any],
    actor_name: str,
    direction: str = "",
    notification_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    rows = resource_rows(payload, resource)
    now = unix_now()

    if resource == "dining_places":
        if record_id is None:
            raise missing_record_id()
        place = find_resource_record(rows, record_id, resource)
        payload[resource] = rows
        if action == "book":
            customer = str(data.get("customer_name") or "").strip()[:80]
            booking_date = str(data.get("booking_date") or "").strip()[:10]
            booking_time = str(data.get("booking_time") or "").strip()[:5]
            if not customer or not booking_date or not booking_time:
                raise ApiError(
                    400,
                    "dining_booking_fields_required",
                    "Mijoz ismi, sana va vaqtni kiriting.",
                )
            orders = resource_rows(payload, "dining_orders")
            orders.append({
                "id": next_record_id(orders),
                "place_id": place["id"],
                "kind": "booking",
                "customer_name": customer,
                "phone": str(data.get("phone") or "").strip()[:30],
                "booking_date": booking_date,
                "booking_time": booking_time,
                "guests": max(
                    1,
                    min(100, integer_or_default(data.get("guests"), 1)),
                ),
                "note": str(data.get("note") or "").strip()[:300],
                "total": 0,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            })
            payload["dining_orders"] = orders
        elif action == "create_order":
            prepared = dining_prepared_items(
                payload,
                data.get("items"),
                empty_message="Zakaz uchun mahsulot tanlanmadi.",
                missing_message="Tanlangan mahsulotlar topilmadi.",
            )
            orders = resource_rows(payload, "dining_orders")
            total = sum(integer(item.get("total")) for item in prepared)
            order_id = next_record_id(orders)
            orders.append({
                "id": order_id,
                "place_id": place["id"],
                "kind": "order",
                "customer_name": str(data.get("customer_name") or "").strip()[:80],
                "note": str(data.get("note") or "").strip()[:300],
                "total": total,
                "waiter_staff_id": None,
                "waiter_name": str(actor_name or "Rahbar")[:80],
                "problem_open": 0,
                "kitchen_status": "preparing",
                "payment_status": "open",
                "status": "active",
                "items": prepared,
                "created_at": now,
                "updated_at": now,
            })
            payload["dining_orders"] = orders
            append_dining_notification(
                payload,
                title="Yangi ichki zakaz",
                body=f"{place.get('name') or 'Stol'} · {total} so'm",
                action_type="dining_kitchen",
                order_id=order_id,
                target_perm="kitchen",
                now=now,
            )
            append_dining_notification(
                payload,
                title="Yangi ochiq hisob",
                body=f"{place.get('name') or 'Stol'} · {total} so'm",
                action_type="dining_cash",
                order_id=order_id,
                target_perm="kassa",
                now=now,
            )
        elif action == "clear":
            orders = resource_rows(payload, "dining_orders")
            unfinished = any(
                str(order.get("place_id")) == str(place["id"])
                and order.get("kind") == "order"
                and order.get("status") == "active"
                and (
                    order.get("payment_status") != "confirmed"
                    or order.get("kitchen_status") != "done"
                )
                for order in orders
            )
            if unfinished:
                raise ApiError(
                    409,
                    "dining_place_has_unfinished_order",
                    "Stolni bo'shatish uchun taom tayyor va to'lov "
                    "tasdiqlangan bo'lishi kerak.",
                )
            for order in orders:
                if (
                    str(order.get("place_id")) == str(place["id"])
                    and order.get("status") == "active"
                ):
                    order["status"] = "done"
                    order["updated_at"] = now
            payload["dining_orders"] = orders
        else:
            raise action_forbidden()
        sync_dining_place_activity(payload)
        return find_record(resource_rows(payload, resource), record_id)

    if resource == "dining_orders" and action == "add_items":
        if record_id is None:
            raise missing_record_id()
        try:
            item = find_record(rows, record_id)
        except ApiError:
            raise ApiError(
                404,
                "dining_order_not_found",
                "Ichki buyurtma topilmadi.",
            ) from None
        if item.get("kind") != "order":
            raise ApiError(404, "dining_order_not_found", "Ichki buyurtma topilmadi.")
        if (
            item.get("status") != "active"
            or item.get("payment_status") == "confirmed"
        ):
            raise ApiError(
                400,
                "completed_dining_order",
                "Yakunlangan hisobga taom qo'shib bo'lmaydi.",
            )
        prepared = dining_prepared_items(
            payload,
            data.get("items"),
            empty_message="Qo'shiladigan taom tanlanmadi.",
            missing_message="Tanlangan taomlar topilmadi.",
        )
        current_items = item.get("items")
        item["items"] = [
            *(
                value
                for value in (
                    current_items if isinstance(current_items, list) else []
                )
                if isinstance(value, dict)
            ),
            *prepared,
        ]
        added = sum(integer(value.get("total")) for value in prepared)
        item["total"] = integer(item.get("total")) + added
        item["kitchen_status"] = "preparing"
        item["updated_at"] = now
        payload[resource] = rows
        place = next(
            (
                value
                for value in resource_rows(payload, "dining_places")
                if str(value.get("id")) == str(item.get("place_id"))
            ),
            {},
        )
        place_name = str(place.get("name") or "Stol")
        append_dining_notification(
            payload,
            title="Ichki zakazga yangi taom qo'shildi",
            body=f"{place_name} · +{added} so'm",
            action_type="dining_kitchen",
            order_id=integer(item.get("id")),
            target_perm="kitchen",
            now=now,
        )
        append_dining_notification(
            payload,
            title="Ichki zakaz hisobi yangilandi",
            body=f"{place_name} · +{added} so'm",
            action_type="dining_cash",
            order_id=integer(item.get("id")),
            target_perm="kassa",
            now=now,
        )
        sync_dining_place_activity(payload)
        return item

    if resource == "medical_queue":
        return apply_medical_queue_action(
            payload,
            action,
            record_id=record_id,
            data=data,
            direction=direction,
            notification_events=(
                notification_events if notification_events is not None else []
            ),
            now=now,
        )

    if resource == "education_enrollments":
        return apply_education_enrollment_action(
            payload,
            action,
            record_id=record_id,
            data=data,
            now=now,
        )

    if resource == "notifications" and action == "mark_all_read":
        for row in rows:
            row["is_read"] = 1
            row["read_at"] = now
        payload[resource] = rows
        return None

    if resource == "following" and action == "unfollow":
        if record_id is None:
            raise missing_record_id()
        rows.pop(find_record_index(rows, record_id))
        payload[resource] = rows
        return None

    if resource == "business_subscriptions" and action == "request_plan":
        plan = str(data.get("plan") or "").casefold()
        duration = int(data.get("duration_months") or 1)
        if plan not in {"free", "plus", "pro"} or duration not in {1, 3, 12}:
            raise ApiError(422, "invalid_subscription_plan", "Tarif yoki muddat noto‘g‘ri.")
        status = "active" if plan == "free" else "pending_payment"
        item = {
            "id": next_record_id(rows),
            "plan": plan,
            "duration_months": duration,
            "status": status,
            "created_at": now,
            "updated_at": now,
        }
        rows.append(item)
        payload[resource] = rows
        if plan != "free":
            payments = resource_rows(payload, "subscription_payments")
            payments.append(
                {
                    "id": next_record_id(payments),
                    "plan": plan,
                    "duration_months": duration,
                    "amount_snapshot": max(0, int(data.get("amount") or 0)),
                    "status": "draft",
                    "created_at": now,
                    "updated_at": now,
                    "attempts": [],
                    "events": [],
                }
            )
            payload["subscription_payments"] = payments
        return item

    if resource == "messages" and action == "send":
        text = str(data.get("text") or "").strip()
        if not text:
            raise ApiError(422, "message_text_required", "Xabar matnini kiriting.")
        item = {
            "id": next_record_id(rows),
            "text": text,
            "sender_kind": "business",
            "created_at": now,
            "updated_at": now,
        }
        for key in (
            "order_id",
            "thread_id",
            "receiver_id",
            "receiver_kind",
            "reply_to_id",
        ):
            if key in data:
                item[key] = data[key]
        if data.get("reply_to_id") is not None:
            try:
                reply = find_record(rows, data["reply_to_id"])
            except ApiError:
                reply = None
            if reply is not None:
                item["reply"] = {
                    "id": reply.get("id"),
                    "sender_name": reply.get("sender_name") or "Xabar",
                    "text": reply.get("text") or "",
                    "media_type": reply.get("media_type") or "text",
                }
        rows.append(item)
        payload[resource] = rows
        return item

    if record_id is None:
        raise missing_record_id()
    item = find_record(rows, record_id)

    if resource == "subscription_payments" and action == "resubmit":
        receipt_type = str(data.get("receipt_type") or "")
        receipt_size = integer(data.get("receipt_size"))
        receipt_name = str(data.get("receipt_name") or "").strip()[:240]
        if (
            receipt_type not in {"image/jpeg", "image/png", "image/webp"}
            or receipt_size <= 0
            or receipt_size > 5 * 1024 * 1024
            or not receipt_name
        ):
            raise ApiError(
                422,
                "invalid_payment_receipt",
                "JPG, PNG yoki WEBP; maksimum 5 MB.",
            )
        attempts = item.get("attempts")
        if not isinstance(attempts, list):
            attempts = []
        attempts.append({
            "submitted_at": now,
            "receipt_name": receipt_name,
            "receipt_type": receipt_type,
            "receipt_size": receipt_size,
        })
        item["attempts"] = attempts
        item["status"] = "pending"
        item.pop("reason", None)
        item.pop("rejection_reason", None)
    elif resource == "orders" and action == "report_problem":
        item["problem_open"] = 1
        item["problem_reason"] = str(data.get("reason") or "other")[:80]
        item["problem_note"] = str(data.get("note") or "").strip()[:500]
    elif resource == "orders" and action == "handoff":
        status = str(item.get("status") or "")
        order_type = str(item.get("order_type") or "")
        if status not in {"handoff_waiting_seller", "ready", "tayyor"}:
            raise ApiError(
                422,
                "order_not_ready_for_handoff",
                "Buyurtma topshirishga tayyor emas.",
            )
        item["status"] = (
            "pickup_waiting_customer"
            if order_type == "pickup" or status in {"ready", "tayyor"}
            else "in_delivery"
        )
    elif resource == "messages" and action == "delete":
        item["is_deleted"] = 1
        item["deleted_at"] = now
    elif resource == "notifications" and action == "mark_read":
        item["is_read"] = 1
        item["read_at"] = now
    elif resource == "business_reviews" and action == "reply":
        reply = str(data.get("reply") or "").strip()
        if not reply:
            raise ApiError(422, "review_reply_required", "Javob matnini kiriting.")
        item["business_reply"] = reply
        item["reply"] = reply
        item["business_reply_at"] = now
    elif action == "set_status" and resource in {
        "orders",
        "listings",
        "advertisements",
        "stories",
    }:
        status = str(data.get("status") or "").casefold()
        allowed = ORDER_STATUSES if resource == "orders" else GENERIC_STATUSES
        if status not in allowed:
            raise ApiError(422, "invalid_status", "Tanlangan holat ruxsat etilmagan.")
        item["status"] = status
    elif resource == "stories" and action == "archive":
        item["status"] = "archived"
        item["archived_at"] = now
    else:
        raise action_forbidden()

    item["updated_at"] = now
    payload[resource] = rows
    return item


def missing_record_id() -> ApiError:
    return ApiError(422, "record_id_required", "Amal uchun yozuv IDsi kerak.")


def action_forbidden() -> ApiError:
    return ApiError(
        403,
        "business_online_action_forbidden",
        "Bu bo‘limda tanlangan amal ruxsat etilmagan.",
    )


def apply_education_enrollment_action(
    payload: dict[str, Any],
    action: str,
    *,
    record_id: int | str | None,
    data: dict[str, Any],
    now: int,
) -> dict[str, Any]:
    if record_id is None:
        raise missing_record_id()
    rows = raw_payload_rows(payload, "education_enrollments")
    try:
        enrollment = find_record(rows, record_id)
    except ApiError:
        raise ApiError(404, "new_education_enrollment_not_found", "Yangi ariza topilmadi.") from None
    if str(enrollment.get("status") or "") != "new":
        raise ApiError(404, "new_education_enrollment_not_found", "Yangi ariza topilmadi.")

    if action == "accept":
        group_id = integer(data.get("group_id"))
        group = next(
            (
                row
                for row in raw_payload_rows(payload, "education_groups")
                if integer(row.get("id")) == group_id
                and str(row.get("status") or "") == "active"
            ),
            None,
        )
        if group is None:
            raise ApiError(400, "education_group_required", "Guruhni tanlang.")
        course_id = integer(enrollment.get("course_item_id"))
        group_course_id = integer(group.get("course_item_id"))
        if group_course_id and group_course_id != course_id:
            raise ApiError(
                400,
                "education_group_course_mismatch",
                "Tanlangan guruh boshqa kursga tegishli.",
            )

        students = raw_payload_rows(payload, "education_students")
        user_id = integer(enrollment.get("user_id"))
        student = next(
            (
                row
                for row in students
                if user_id
                and integer(row.get("user_id")) == user_id
                and str(row.get("status") or "") == "active"
            ),
            None,
        )
        if student is None:
            student = {
                "id": next_record_id(students),
                "group_id": group_id,
                "user_id": enrollment.get("user_id"),
                "full_name": str(enrollment.get("customer_name") or ""),
                "phone": str(enrollment.get("phone") or ""),
                "joined_date": (
                    datetime.now(UTC) + timedelta(hours=5)
                ).strftime("%Y-%m-%d"),
                "note": (
                    "Kurs arizasi: " + str(enrollment.get("note") or "")
                )[:500],
                "monthly_fee": 0,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
            students.append(student)
        else:
            student["group_id"] = group_id
            student["phone"] = str(enrollment.get("phone") or "")
            student["updated_at"] = now
        payload["education_students"] = students
        enrollment["status"] = "accepted"
        enrollment["group_id"] = group_id
        enrollment["student_id"] = student["id"]
    elif action == "reject":
        enrollment["status"] = "rejected"
    else:
        raise action_forbidden()

    enrollment["updated_at"] = now
    payload["education_enrollments"] = rows
    return find_record(education_enrollment_rows(payload), record_id)


def apply_medical_queue_action(
    payload: dict[str, Any],
    action: str,
    *,
    record_id: int | str | None,
    data: dict[str, Any],
    direction: str,
    notification_events: list[dict[str, Any]],
    now: int,
) -> dict[str, Any] | None:
    rows = raw_payload_rows(payload, "medical_queue")
    if action == "offline_add":
        item_id = integer(data.get("item_id"))
        staff_id = integer(data.get("staff_id"))
        service, provider = medical_queue_provider(
            payload,
            item_id=item_id,
            staff_id=staff_id,
        )
        queue_date = str(data.get("queue_date") or "")[:10]
        today = (datetime.now(UTC) + timedelta(hours=5)).strftime("%Y-%m-%d")
        if queue_date < today:
            raise ApiError(
                400,
                "past_medical_queue_date",
                "O'tgan sanaga navbat olib bo'lmaydi.",
            )
        slot_time = str(data.get("slot_time") or "").strip()
        mode = str(provider.get("mode") or "live")
        if mode == "slot":
            if not re.fullmatch(r"\d{2}:\d{2}", slot_time):
                raise ApiError(
                    400,
                    "medical_slot_required",
                    "Qabul vaqtini tanlang.",
                )
            slots = generated_medical_slots(
                str(provider.get("work_start") or "08:00"),
                str(provider.get("work_end") or "17:00"),
                integer_or_default(provider.get("avg_minutes"), 20),
            )
            if slot_time not in slots:
                raise ApiError(
                    400,
                    "medical_slot_outside_schedule",
                    "Bu vaqt qabul jadvalida yo'q.",
                )
            if any(
                str(row.get("item_id")) == str(item_id)
                and str(row.get("staff_id")) == str(staff_id)
                and str(row.get("queue_date")) == queue_date
                and str(row.get("slot_time")) == slot_time
                and str(row.get("status")) in {
                    "waiting", "called", "in_service", "done"
                }
                for row in rows
            ):
                raise ApiError(
                    409,
                    "medical_slot_taken",
                    "Bu vaqt band qilindi. Boshqa vaqt tanlang.",
                )
            queue_no = slot_minutes(slot_time) or 0
            queue_code = f"{medical_code(service.get('name'))}-{slot_time.replace(':', '')}"
        else:
            queue_no = max(
                [
                    integer(row.get("queue_no"))
                    for row in rows
                    if str(row.get("item_id")) == str(item_id)
                    and str(row.get("staff_id")) == str(staff_id)
                    and str(row.get("queue_date")) == queue_date
                    and not str(row.get("slot_time") or "")
                ],
                default=0,
            ) + 1
            queue_code = f"{medical_code(service.get('name'))}-{queue_no:03d}"
        item = {
            "id": next_record_id(rows),
            "item_id": item_id,
            "staff_id": staff_id,
            "user_id": None,
            "patient_name": str(data.get("patient_name") or "").strip()[:120],
            "phone": str(data.get("phone") or "")[:32],
            "queue_date": queue_date,
            "queue_no": queue_no,
            "queue_code": queue_code,
            "source": "offline",
            "status": "waiting",
            "note": str(data.get("note") or "")[:200],
            "slot_time": slot_time,
            "created_at": now,
            "updated_at": now,
        }
        rows.append(item)
        payload["medical_queue"] = rows
        return find_record(medical_queue_rows(payload), item["id"])

    if record_id is None:
        raise missing_record_id()
    item = find_resource_record(rows, record_id, "medical_queue")

    if action == "set_status":
        status = str(data.get("status") or "")
        if status not in MEDICAL_QUEUE_STATUSES:
            raise ApiError(
                400,
                "invalid_medical_queue_status",
                "Navbat holati noto'g'ri.",
            )
        old_status = str(item.get("status") or "")
        if old_status in MEDICAL_QUEUE_TERMINAL and status in {
            "waiting", "called", "in_service"
        }:
            raise ApiError(
                400,
                "completed_medical_queue",
                "Yakunlangan navbatni qayta faollashtirib bo'lmaydi.",
            )
        item["status"] = status
        item["updated_at"] = now
        payload["medical_queue"] = rows
        append_medical_queue_history(
            payload,
            item,
            action="status",
            old_value=old_status,
            new_value=status,
            now=now,
        )
        if status == "called":
            labels = medical_queue_labels(direction)
            queue_notification_event(
                notification_events,
                item,
                event="called",
                title="Navbatingiz keldi",
                body=(
                    f"{item.get('queue_code')} navbat {labels['called_by']} "
                    "tomonidan chaqirildi."
                ),
                action_type="medical_queue_called",
            )
            next_row = next_waiting_medical_queue(rows, item)
            if next_row is not None:
                queue_notification_event(
                    notification_events,
                    next_row,
                    event=f"soon:{item.get('queue_no')}",
                    title="Navbatingiz yaqinlashdi",
                    body=(
                        f"Tayyorlaning — {next_row.get('queue_code')} "
                        "navbatgacha 1 kishi qoldi."
                    ),
                    action_type="medical_queue_soon",
                )
        elif status == "cancelled":
            queue_notification_event(
                notification_events,
                item,
                event="cancelled",
                title="Navbat bekor qilindi",
                body=(
                    f"{item.get('queue_code')} navbat muassasa tomonidan "
                    "bekor qilindi."
                ),
                action_type="medical_queue_cancelled",
            )
        return find_record(medical_queue_rows(payload), record_id)

    if action == "swap":
        other_id = integer(data.get("other_queue_id"))
        try:
            other = find_record(rows, other_id)
        except ApiError:
            other = None
        same_queue = other is not None and other is not item and (
            str(item.get("queue_date")),
            str(item.get("staff_id")),
            str(item.get("item_id")),
        ) == (
            str(other.get("queue_date")),
            str(other.get("staff_id")),
            str(other.get("item_id")),
        )
        if not same_queue or other is None:
            provider = medical_queue_labels(direction)["provider"].lower()
            raise ApiError(
                400,
                "medical_queue_swap_mismatch",
                f"Faqat bir xil xizmat va {provider}ning ikkita navbati "
                "almashtiriladi.",
            )
        service = next(
            (
                row
                for row in raw_payload_rows(payload, "items")
                if str(row.get("id")) == str(item.get("item_id"))
            ),
            {},
        )
        prefix = medical_code(service.get("name"))
        first_number = integer(item.get("queue_no"))
        second_number = integer(other.get("queue_no"))
        item["queue_no"] = second_number
        item["queue_code"] = f"{prefix}-{second_number:03d}"
        item["updated_at"] = now
        other["queue_no"] = first_number
        other["queue_code"] = f"{prefix}-{first_number:03d}"
        other["updated_at"] = now
        payload["medical_queue"] = rows
        append_medical_queue_history(
            payload,
            item,
            action="swap",
            old_value=str(first_number),
            new_value=str(second_number),
            now=now,
        )
        queue_notification_event(
            notification_events,
            item,
            event=f"changed:{item.get('queue_no')}:{now}",
            title="Navbat raqami o‘zgardi",
            body=f"Yangi navbat raqamingiz: {item.get('queue_code')}.",
            action_type="medical_queue_changed",
        )
        queue_notification_event(
            notification_events,
            other,
            event=f"changed:{other.get('queue_no')}:{now}",
            title="Navbat raqami o‘zgardi",
            body=f"Yangi navbat raqamingiz: {other.get('queue_code')}.",
            action_type="medical_queue_changed",
        )
        return find_record(medical_queue_rows(payload), record_id)

    raise action_forbidden()


def medical_queue_provider(
    payload: dict[str, Any],
    *,
    item_id: int,
    staff_id: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    service = next(
        (
            row
            for row in raw_payload_rows(payload, "items")
            if integer(row.get("id")) == item_id
            and str(row.get("kind") or "") == "service"
            and queue_enabled(row.get("queue_enabled"))
        ),
        None,
    )
    if service is None:
        raise ApiError(
            400,
            "medical_queue_service_disabled",
            "Bu xizmat uchun navbat yoqilmagan.",
        )
    linked = any(
        integer(row.get("staff_id")) == staff_id
        and integer(row.get("item_id")) == item_id
        and bool(integer_or_default(row.get("active"), 1))
        for row in raw_payload_rows(payload, "medical_doctor_services")
    )
    provider = next(
        (
            row
            for row in raw_payload_rows(payload, "medical_doctors")
            if integer(row.get("staff_id")) == staff_id
            and str(row.get("status") or "active") == "active"
        ),
        None,
    )
    active_staff = any(
        integer(row.get("id")) == staff_id
        for row in medical_staff_rows(payload)
    )
    if not linked or provider is None or not active_staff:
        raise ApiError(
            400,
            "medical_provider_not_assigned",
            "Xizmat ko'rsatuvchi hali biriktirilmagan.",
        )
    return service, provider


def medical_code(name: Any) -> str:
    letters = "".join(
        character
        for character in str(name or "").upper()
        if character.isalnum()
    )[:3]
    return letters or "NAV"


def slot_minutes(value: Any) -> int | None:
    try:
        hour, minute = str(value).split(":")
        return int(hour) * 60 + int(minute)
    except (TypeError, ValueError):
        return None


def generated_medical_slots(start: str, end: str, step: int) -> list[str]:
    first = slot_minutes(start)
    last = slot_minutes(end)
    interval = max(5, integer_or_default(step, 20))
    if first is None or last is None or first >= last:
        return []
    result = []
    current = first
    while current + interval <= last:
        result.append(f"{current // 60:02d}:{current % 60:02d}")
        current += interval
    return result


def medical_queue_labels(direction: str) -> dict[str, str]:
    if str(direction or "").strip() == "Tibbiy xizmatlar":
        return {
            "provider": "Shifokor",
            "customer": "Bemor",
            "called_by": "shifokor",
        }
    return {
        "provider": "Xizmat ko'rsatuvchi",
        "customer": "Mijoz",
        "called_by": "xizmat ko'rsatuvchi",
    }


def append_medical_queue_history(
    payload: dict[str, Any],
    queue: dict[str, Any],
    *,
    action: str,
    old_value: str,
    new_value: str,
    now: int,
) -> None:
    rows = raw_payload_rows(payload, "medical_queue_history")
    rows.append({
        "id": next_record_id(rows),
        "queue_id": queue.get("id"),
        "action": action,
        "old_value": old_value,
        "new_value": new_value,
        "created_at": now,
    })
    payload["medical_queue_history"] = rows


def next_waiting_medical_queue(
    rows: list[dict[str, Any]],
    current: dict[str, Any],
) -> dict[str, Any] | None:
    candidates = [
        row
        for row in rows
        if str(row.get("item_id")) == str(current.get("item_id"))
        and str(row.get("staff_id")) == str(current.get("staff_id"))
        and str(row.get("queue_date")) == str(current.get("queue_date"))
        and str(row.get("status")) == "waiting"
        and integer(row.get("queue_no")) > integer(current.get("queue_no"))
    ]
    return min(candidates, key=lambda row: integer(row.get("queue_no"))) if candidates else None


def queue_notification_event(
    events: list[dict[str, Any]],
    queue: dict[str, Any],
    *,
    event: str,
    title: str,
    body: str,
    action_type: str,
) -> None:
    user_id = integer(queue.get("user_id"))
    queue_id = integer(queue.get("id"))
    if not user_id or not queue_id:
        return
    events.append({
        "user_id": user_id,
        "event_key": f"medical_queue:{queue_id}:{event}",
        "title": title,
        "body": body,
        "action_type": action_type,
        "medical_queue_id": queue_id,
    })


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
            not bool(integer(row.get("is_read")))
            for row in notifications
        )
        profile.dashboard_snapshot = snapshot
        profile.cabinet_payload = payload


def append_medical_user_notification(
    payload: dict[str, Any],
    event: dict[str, Any],
) -> None:
    notifications = raw_payload_rows(payload, "notifications")
    event_key = str(event.get("event_key") or "")
    if any(str(row.get("event_key") or "") == event_key for row in notifications):
        return
    now = unix_now()
    notifications.append({
        "id": next_record_id(notifications),
        "actor_kind": "user",
        "actor_id": integer(event.get("user_id")),
        "event_key": event_key,
        "title": str(event.get("title") or ""),
        "body": str(event.get("body") or ""),
        "medical_queue_id": integer(event.get("medical_queue_id")),
        "requires_action": 1,
        "action_type": str(event.get("action_type") or ""),
        "is_read": 0,
        "created_at": now,
        "updated_at": now,
    })
    payload["notifications"] = notifications


def dining_prepared_items(
    payload: dict[str, Any],
    incoming: Any,
    *,
    empty_message: str,
    missing_message: str,
) -> list[dict[str, Any]]:
    wanted: dict[int, float] = {}
    values = incoming if isinstance(incoming, list) else []
    for value in values[:100]:
        if not isinstance(value, dict):
            continue
        try:
            item_id = int(value.get("item_id"))
            quantity = max(0.01, min(999.0, float(value.get("qty") or 0)))
        except (TypeError, ValueError):
            continue
        wanted[item_id] = wanted.get(item_id, 0.0) + quantity
    if not wanted:
        raise ApiError(400, "dining_items_required", empty_message)

    prepared = []
    for item in resource_rows(payload, "items"):
        item_id = integer(item.get("id"))
        if (
            item_id not in wanted
            or str(item.get("stock_type") or "ready_food") != "ready_food"
        ):
            continue
        quantity = wanted[item_id]
        price = parse_price_amount(item.get("price"))
        line_total = int(round(price * quantity))
        prepared.append({
            "item_id": item_id,
            "name": str(item.get("name") or ""),
            "qty": quantity,
            "unit": str(item.get("unit") or "dona"),
            "price": price,
            "total": line_total,
        })
    if not prepared:
        raise ApiError(400, "dining_items_not_found", missing_message)
    return prepared


def append_dining_notification(
    payload: dict[str, Any],
    *,
    title: str,
    body: str,
    action_type: str,
    order_id: int,
    target_perm: str,
    now: int,
) -> None:
    notifications = resource_rows(payload, "notifications")
    notifications.append({
        "id": next_record_id(notifications),
        "title": title,
        "body": body,
        "action_type": action_type,
        "dining_order_id": order_id,
        "target_perm": target_perm,
        "is_read": 0,
        "created_at": now,
        "updated_at": now,
    })
    payload["notifications"] = notifications


DINING_ACTIVE_FIELDS = {
    "active_id",
    "active_kind",
    "customer_name",
    "booking_date",
    "booking_time",
    "guests",
    "total",
}


def sync_dining_place_activity(payload: dict[str, Any]) -> None:
    if "dining_places" not in payload and "dining_orders" not in payload:
        return
    places = resource_rows(payload, "dining_places")
    orders = resource_rows(payload, "dining_orders")
    for place in places:
        for key in DINING_ACTIVE_FIELDS:
            place.pop(key, None)
        active = [
            order
            for order in orders
            if str(order.get("place_id")) == str(place.get("id"))
            and order.get("status") == "active"
        ]
        if not active:
            continue
        latest = max(active, key=lambda order: integer(order.get("id")))
        place.update({
            "active_id": latest.get("id"),
            "active_kind": latest.get("kind"),
            "customer_name": latest.get("customer_name"),
            "booking_date": latest.get("booking_date"),
            "booking_time": latest.get("booking_time"),
            "guests": latest.get("guests"),
            "total": latest.get("total"),
        })
    payload["dining_places"] = places


def refresh_derived(profile: BusinessProfile, payload: dict[str, Any]) -> None:
    sync_dining_place_activity(payload)
    followers = resource_rows(payload, "followers")
    following = resource_rows(payload, "following")
    reviews = resource_rows(payload, "business_reviews")
    notifications = resource_rows(payload, "notifications")
    orders = resource_rows(payload, "orders")

    profile.followers_count = len(followers)
    profile.following_count = len(following)
    ratings = [integer(row.get("rating") or row.get("stars")) for row in reviews]
    profile.rating_sum = sum(value for value in ratings if value > 0)
    profile.rating_count = sum(value > 0 for value in ratings)

    snapshot = deepcopy(profile.dashboard_snapshot or {})
    snapshot["new_orders"] = sum(
        str(row.get("status") or "") == "new" for row in orders
    )
    snapshot["active_orders"] = sum(
        str(row.get("status") or "") not in TERMINAL_ORDER_STATUSES
        for row in orders
    )
    snapshot["problem_orders"] = sum(bool(row.get("problem_open")) for row in orders)
    snapshot["unread"] = sum(not bool(integer(row.get("is_read"))) for row in notifications)
    snapshot["followers"] = len(followers)
    snapshot["occupied_places"] = sum(
        bool(row.get("active_id"))
        for row in resource_rows(payload, "dining_places")
    )
    snapshot["service_active"] = sum(
        str(row.get("status") or "") in {"waiting", "called", "in_service"}
        for row in raw_payload_rows(payload, "medical_queue")
    )
    profile.dashboard_snapshot = snapshot

    ordered = sorted(
        orders,
        key=lambda row: integer(row.get("updated_at") or row.get("created_at")),
        reverse=True,
    )
    profile.recent_activity = [
        {
            "id": integer(row.get("id")),
            "kind": "service" if order_is_service(row) else "order",
            "title": str(row.get("title") or row.get("name") or "Buyurtma"),
            "status": str(row.get("status") or ""),
            "amount": integer(row.get("total_amount") or row.get("total")),
            "created_at": integer(row.get("created_at")),
        }
        for row in ordered[:5]
    ]


def order_is_service(row: dict[str, Any]) -> bool:
    return str(
        row.get("order_type") or row.get("kind") or row.get("order_category") or ""
    ) in {"booking", "service", "queue", "medical"}


def integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def integer_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_price_amount(value: Any) -> int:
    digits = "".join(character for character in str(value or "") if character.isdigit())
    return int(digits[:12]) if digits else 0


def unix_now() -> int:
    return int(datetime.now(UTC).timestamp())
