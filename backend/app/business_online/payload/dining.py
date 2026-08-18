"""Ovqatlanish resurslari: tayyorlangan taomlar va stol faolligi."""

from __future__ import annotations

from typing import Any

from app.business_online.payload.constants import (
    DINING_ACTIVE_FIELDS,
)
from app.business_online.payload.helpers import (
    action_forbidden,
    find_record,
    find_resource_record,
    integer,
    integer_or_default,
    missing_record_id,
    next_record_id,
    parse_price_amount,
)
from app.business_online.payload.spec import (
    resource_rows,
)
from app.core.errors import ApiError


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
        line_total = round(price * quantity)
        prepared.append(
            {
                "item_id": item_id,
                "name": str(item.get("name") or ""),
                "qty": quantity,
                "unit": str(item.get("unit") or "dona"),
                "price": price,
                "total": line_total,
            }
        )
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
    notifications.append(
        {
            "id": next_record_id(notifications),
            "title": title,
            "body": body,
            "action_type": action_type,
            "dining_order_id": order_id,
            "target_perm": target_perm,
            "is_read": 0,
            "created_at": now,
            "updated_at": now,
        }
    )
    payload["notifications"] = notifications


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
        place.update(
            {
                "active_id": latest.get("id"),
                "active_kind": latest.get("kind"),
                "customer_name": latest.get("customer_name"),
                "booking_date": latest.get("booking_date"),
                "booking_time": latest.get("booking_time"),
                "guests": latest.get("guests"),
                "total": latest.get("total"),
            }
        )
    payload["dining_places"] = places


def apply_dining_action(
    payload: dict[str, Any],
    resource: str,
    action: str,
    *,
    record_id: int | str | None,
    data: dict[str, Any],
    actor_name: str,
    now: int,
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Stol va ichki zakaz amallari.

    Ilgari `apply_action` ichida edi va o'sha funksiyani 400 qatordan
    oshirib yuborardi. Bu ikki shox boshqa hech narsaga tegmaydi —
    faqat `payload` ni o'zgartiradi va yangilangan yozuvni qaytaradi.
    """

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
            orders.append(
                {
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
                }
            )
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
            orders.append(
                {
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
                }
            )
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
        if item.get("status") != "active" or item.get("payment_status") == "confirmed":
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
                for value in (current_items if isinstance(current_items, list) else [])
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

    return None
