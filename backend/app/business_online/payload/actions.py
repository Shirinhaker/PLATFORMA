"""Amal dispetcheri: `apply_action` qaysi domenga yo'naltirishni biladi."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.business_online.payload.advertisements import (
    advertisement_pricing,
)
from app.business_online.payload.constants import (
    GENERIC_STATUSES,
    ORDER_STATUSES,
    TERMINAL_ORDER_STATUSES,
)
from app.business_online.payload.dining import (
    apply_dining_action,
    sync_dining_place_activity,
)
from app.business_online.payload.education import (
    apply_education_enrollment_action,
)
from app.business_online.payload.helpers import (
    action_forbidden,
    find_record,
    find_record_index,
    integer,
    missing_record_id,
    next_record_id,
    order_is_service,
    raw_payload_rows,
    unix_now,
)
from app.business_online.payload.medical_queue import (
    apply_medical_queue_action,
)
from app.business_online.payload.spec import (
    resource_rows,
)
from app.core.errors import ApiError
from app.profiles.model import BusinessProfile


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

    if resource == "dining_places" or (
        resource == "dining_orders" and action == "add_items"
    ):
        return apply_dining_action(
            payload,
            resource,
            action,
            record_id=record_id,
            data=data,
            actor_name=actor_name,
            now=now,
            rows=rows,
        )

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

    if resource == "notifications" and action == "set_push_preferences":
        enabled = 1 if bool(data.get("enabled")) else 0
        orders_enabled = 1 if bool(data.get("orders_enabled")) else 0
        preference = {
            "id": 1,
            "enabled": enabled,
            "orders_enabled": orders_enabled,
            "updated_at": now,
        }
        payload["push_preferences"] = [preference]
        return preference

    if resource == "advertisements" and action == "calculate_price":
        _, pricing = advertisement_pricing(data)
        return pricing

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
            raise ApiError(
                422, "invalid_subscription_plan", "Tarif yoki muddat noto‘g‘ri."
            )
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
        attempts.append(
            {
                "submitted_at": now,
                "receipt_name": receipt_name,
                "receipt_type": receipt_type,
                "receipt_size": receipt_size,
            }
        )
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
        str(row.get("status") or "") not in TERMINAL_ORDER_STATUSES for row in orders
    )
    snapshot["problem_orders"] = sum(bool(row.get("problem_open")) for row in orders)
    snapshot["unread"] = sum(
        not bool(integer(row.get("is_read"))) for row in notifications
    )
    snapshot["followers"] = len(followers)
    snapshot["occupied_places"] = sum(
        bool(row.get("active_id")) for row in resource_rows(payload, "dining_places")
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
