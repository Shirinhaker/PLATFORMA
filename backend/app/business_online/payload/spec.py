"""Resurs ta'rifi: qaysi yo'nalish qaysi resursga tega oladi.

Yaratish va tahrirlashdan oldingi tayyorgarlik, o'chirishdan keyingi
kaskad ham shu yerda.
"""

from __future__ import annotations

from typing import Any

from app.business_online.payload.advertisements import (
    advertisement_pricing,
)
from app.business_online.payload.constants import (
    EDUCATION_RESOURCES,
    MEDICAL_RESOURCES,
    QUEUE_DIRECTIONS,
    RESOURCE_SPECS,
    ResourceSpec,
)
from app.business_online.payload.education import (
    education_enrollment_rows,
    education_group_rows,
)
from app.business_online.payload.helpers import (
    integer_or_default,
    raw_payload_rows,
)
from app.business_online.payload.medical import (
    medical_doctor_rows,
    medical_queue_rows,
    medical_staff_rows,
    prepare_medical_doctor,
)
from app.core.errors import ApiError
from app.profiles.model import BusinessProfile


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
    if resource == "advertisements":
        targets, pricing = advertisement_pricing(clean)
        clean["targets"] = targets
        clean.update(
            {
                "price": pricing["total"],
                "district_count": pricing["district_count"],
                "hours_per_day": pricing["hours_per_day"],
                "duration_days": pricing["duration_days"],
                "district_hour_rate": pricing["district_hour_rate"],
                "billable_district_hours": pricing["billable_district_hours"],
                "price_code": "advertisement_district_hour",
                "status": "payment_pending",
            }
        )
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
    clean.update(
        {
            "kind": kind,
            "name": name or ("Stol" if kind == "table" else "Xona"),
            "seats": (max(0, min(100, seats)) if kind == "table" else 0),
            "x": 4 + (len(rows) % 5) * 18,
            "y": 4,
            "locked": 1,
        }
    )


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


def resource_rows(payload: Any, resource: str) -> list[dict[str, Any]]:
    resource_spec(resource)
    return raw_payload_rows(payload, resource)


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
