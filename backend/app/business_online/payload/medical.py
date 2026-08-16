"""Tibbiyot resurslari: shifokorlar, xodimlar va navbat.

Eng katta bo'lim — navbat holatlari, slotlar va bildirishnomalar.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.business_online.payload.helpers import (
    integer,
    integer_or_default,
    normalized_integer_list,
    queue_enabled,
    raw_payload_rows,
)
from app.core.errors import ApiError


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
        result.append(
            {
                "id": identifier,
                "name": str(row.get("name") or "")[:120],
                "profession": str(row.get("profession") or "Xodim")[:120],
                "status": "active",
            }
        )
    result.sort(key=lambda row: str(row.get("name") or ""))
    return result


def medical_doctor_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    staff = {str(row.get("id")): row for row in medical_staff_rows(payload)}
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
    result.sort(
        key=lambda row: (
            str(row.get("status") or ""),
            str(row.get("name") or ""),
        )
    )
    return result


def medical_queue_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = {str(row.get("id")): row for row in raw_payload_rows(payload, "items")}
    staff = {str(row.get("id")): row for row in medical_staff_rows(payload)}
    result = []
    for source in raw_payload_rows(payload, "medical_queue"):
        row = deepcopy(source)
        item = items.get(str(row.get("item_id")), {})
        provider = staff.get(str(row.get("staff_id")), {})
        row["service_name"] = str(row.get("service_name") or item.get("name") or "")
        row["doctor_name"] = str(row.get("doctor_name") or provider.get("name") or "")
        result.append(row)
    result.sort(
        key=lambda row: (
            integer(row.get("staff_id")),
            integer(row.get("item_id")),
            integer(row.get("queue_no")),
        )
    )
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
        "avg_minutes": max(
            5, min(240, integer_or_default(source.get("avg_minutes"), 20))
        ),
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
    clean.update(
        {
            key: value
            for key, value in prepared.items()
            if key not in {"staff_id", "name", "profession"}
        }
    )


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
    links.extend(
        {
            "business_id": business_id,
            "staff_id": staff_id,
            "item_id": item_id,
            "active": 1,
            "duration_minutes": minutes,
        }
        for item_id in normalized_integer_list(doctor.get("item_ids"))
    )
    payload["medical_doctor_services"] = links


def medical_code(name: Any) -> str:
    letters = "".join(
        character for character in str(name or "").upper() if character.isalnum()
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
