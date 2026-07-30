from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.profiles.model import BusinessProfile


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
    "followers": ResourceSpec(),
    "following": ResourceSpec(delete=True),
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
            return resource_rows(profile.cabinet_payload, resource)

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
            payload = normalized_payload(profile.cabinet_payload)
            rows = resource_rows(payload, resource)
            now = unix_now()
            clean["id"] = next_record_id(rows)
            clean.setdefault("created_at", now)
            clean["updated_at"] = now
            rows.append(clean)
            payload[resource] = rows
            refresh_derived(profile, payload)
            profile.cabinet_payload = payload
            await session.commit()
            return deepcopy(clean), deepcopy(rows)

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
            payload = normalized_payload(profile.cabinet_payload)
            rows = resource_rows(payload, resource)
            item = find_record(rows, record_id)
            item.update(clean)
            item["updated_at"] = unix_now()
            payload[resource] = rows
            refresh_derived(profile, payload)
            profile.cabinet_payload = payload
            await session.commit()
            return deepcopy(item), deepcopy(rows)

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
            payload = normalized_payload(profile.cabinet_payload)
            rows = resource_rows(payload, resource)
            index = find_record_index(rows, record_id)
            rows.pop(index)
            payload[resource] = rows
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
            payload = normalized_payload(profile.cabinet_payload)
            item = apply_action(
                payload,
                resource,
                action,
                record_id=record_id,
                data=clean,
            )
            refresh_derived(profile, payload)
            profile.cabinet_payload = payload
            await session.commit()
            return deepcopy(item), resource_rows(payload, resource)


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
    if not isinstance(payload, dict):
        return []
    value = payload.get(resource)
    if not isinstance(value, list):
        return []
    return [deepcopy(row) for row in value if isinstance(row, dict)]


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


def apply_action(
    payload: dict[str, Any],
    resource: str,
    action: str,
    *,
    record_id: int | str | None,
    data: dict[str, Any],
) -> dict[str, Any] | None:
    rows = resource_rows(payload, resource)
    now = unix_now()

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
        for key in ("order_id", "thread_id", "receiver_id", "receiver_kind"):
            if key in data:
                item[key] = data[key]
        rows.append(item)
        payload[resource] = rows
        return item

    if record_id is None:
        raise missing_record_id()
    item = find_record(rows, record_id)

    if resource == "notifications" and action == "mark_read":
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
        raise ApiError(
            403,
            "business_online_action_forbidden",
            "Bu bo‘limda tanlangan amal ruxsat etilmagan.",
        )

    item["updated_at"] = now
    payload[resource] = rows
    return item


def missing_record_id() -> ApiError:
    return ApiError(422, "record_id_required", "Amal uchun yozuv IDsi kerak.")


def refresh_derived(profile: BusinessProfile, payload: dict[str, Any]) -> None:
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


def unix_now() -> int:
    return int(datetime.now(UTC).timestamp())
