from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from app.business_online.payload.constants import (
    MEDICAL_QUEUE_STATUSES,
    MEDICAL_QUEUE_TERMINAL,
)
from app.business_online.payload.helpers import (
    action_forbidden,
    find_record,
    find_resource_record,
    integer,
    integer_or_default,
    missing_record_id,
    next_record_id,
    queue_enabled,
    raw_payload_rows,
    unix_now,
)
from app.business_online.payload.medical import (
    generated_medical_slots,
    medical_code,
    medical_queue_labels,
    medical_queue_rows,
    medical_staff_rows,
    slot_minutes,
)
from app.core.errors import ApiError


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
                and str(row.get("status"))
                in {"waiting", "called", "in_service", "done"}
                for row in rows
            ):
                raise ApiError(
                    409,
                    "medical_slot_taken",
                    "Bu vaqt band qilindi. Boshqa vaqt tanlang.",
                )
            queue_no = slot_minutes(slot_time) or 0
            queue_code = (
                f"{medical_code(service.get('name'))}-{slot_time.replace(':', '')}"
            )
        else:
            queue_no = (
                max(
                    [
                        integer(row.get("queue_no"))
                        for row in rows
                        if str(row.get("item_id")) == str(item_id)
                        and str(row.get("staff_id")) == str(staff_id)
                        and str(row.get("queue_date")) == queue_date
                        and not str(row.get("slot_time") or "")
                    ],
                    default=0,
                )
                + 1
            )
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
            "waiting",
            "called",
            "in_service",
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
                    f"{item.get('queue_code')} navbat muassasa tomonidan bekor qilindi."
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
        same_queue = (
            other is not None
            and other is not item
            and (
                str(item.get("queue_date")),
                str(item.get("staff_id")),
                str(item.get("item_id")),
            )
            == (
                str(other.get("queue_date")),
                str(other.get("staff_id")),
                str(other.get("item_id")),
            )
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
        integer(row.get("id")) == staff_id for row in medical_staff_rows(payload)
    )
    if not linked or provider is None or not active_staff:
        raise ApiError(
            400,
            "medical_provider_not_assigned",
            "Xizmat ko'rsatuvchi hali biriktirilmagan.",
        )
    return service, provider


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
    rows.append(
        {
            "id": next_record_id(rows),
            "queue_id": queue.get("id"),
            "action": action,
            "old_value": old_value,
            "new_value": new_value,
            "created_at": now,
        }
    )
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
    return (
        min(candidates, key=lambda row: integer(row.get("queue_no")))
        if candidates
        else None
    )


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
    events.append(
        {
            "user_id": user_id,
            "event_key": f"medical_queue:{queue_id}:{event}",
            "title": title,
            "body": body,
            "action_type": action_type,
            "medical_queue_id": queue_id,
        }
    )


def append_medical_user_notification(
    payload: dict[str, Any],
    event: dict[str, Any],
) -> None:
    notifications = raw_payload_rows(payload, "notifications")
    event_key = str(event.get("event_key") or "")
    if any(str(row.get("event_key") or "") == event_key for row in notifications):
        return
    now = unix_now()
    notifications.append(
        {
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
        }
    )
    payload["notifications"] = notifications
