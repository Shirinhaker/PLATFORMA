"""Bildirishnoma jadvallari uchun tur o'girish yordamchilari."""

from __future__ import annotations

from typing import Any

from app.notifications.model import (
    Notification,
)

ROW_COLUMNS = frozenset(
    {
        "id",
        "event_key",
        "title",
        "body",
        "order_id",
        "listing_id",
        "dining_order_id",
        "medical_queue_id",
        "ride_id",
        "target_staff_id",
        "target_permission",
        "action_type",
        "requires_action",
        "is_read",
        "created_at",
        "read_at",
        "resolved_at",
    }
)


PAYLOAD_COMPAT_COLUMNS = (
    "order_id",
    "listing_id",
    "dining_order_id",
    "medical_queue_id",
    "ride_id",
    "target_staff_id",
    "target_permission",
)


def _integer(value: object, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _boolean(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


def _row(notification: Notification) -> dict[str, Any]:
    result = dict(notification.payload or {})
    result.update(
        {
            "id": notification.id,
            "event_key": notification.event_key,
            "title": notification.title,
            "body": notification.body,
            "order_id": notification.order_id,
            "listing_id": notification.listing_id,
            "dining_order_id": notification.dining_order_id,
            "medical_queue_id": notification.medical_queue_id,
            "ride_id": notification.ride_id,
            "target_staff_id": notification.target_staff_id,
            "target_permission": notification.target_permission,
            "action_type": notification.action_type,
            "requires_action": 1 if notification.requires_action else 0,
            "is_read": 1 if notification.is_read else 0,
            "created_at": notification.created_at,
        }
    )
    if notification.read_at is not None:
        result["read_at"] = notification.read_at
    else:
        result.pop("read_at", None)
    if notification.resolved_at is not None:
        result["resolved_at"] = notification.resolved_at
    else:
        result.pop("resolved_at", None)
    return result
