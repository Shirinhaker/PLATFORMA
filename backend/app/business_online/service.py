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
    "dining_places": ResourceSpec(create=True, update=True, delete=True),
    "dining_orders": ResourceSpec(),
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
            ensure_resource_direction(profile, resource)
            payload = normalized_payload(profile.cabinet_payload)
            sync_dining_place_activity(payload)
            return resource_rows(payload, resource)

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
            prepare_record_for_create(resource, clean, rows)
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
            ensure_resource_direction(profile, resource)
            payload = normalized_payload(profile.cabinet_payload)
            rows = resource_rows(payload, resource)
            item = find_resource_record(rows, record_id, resource)
            prepare_patch_for_resource(resource, item, clean)
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


def prepare_record_for_create(
    resource: str,
    clean: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
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
) -> None:
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
        raise


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
                "waiter_name": "Rahbar",
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
    return int(digits) if digits else 0


def unix_now() -> int:
    return int(datetime.now(UTC).timestamp())
