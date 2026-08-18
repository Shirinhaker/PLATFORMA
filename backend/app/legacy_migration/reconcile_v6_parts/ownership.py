"""Buyurtma va yozuv egaligini aniqlash."""

from __future__ import annotations

from app.legacy_migration.reconcile_v6_parts.constants import (
    SERVICE_ORDER_TYPES,
    TERMINAL_ORDER_STATUSES,
)
from app.legacy_migration.reconcile_v6_parts.helpers import (
    _as_int,
)


def _order_belongs_to_user(row, user_id):
    if "customer_user_id" in row:
        return (
            _as_int(row.get("customer_user_id")) == user_id
            and str(row.get("customer_kind") or "user") == "user"
        )
    return _as_int(row.get("user_id") or row.get("customer_id")) == user_id


def _order_belongs_to_business(row, business_id, owner_user_id):
    if "provider_actor_id" in row:
        return (
            str(row.get("provider_kind") or "business") == "business"
            and _as_int(row.get("provider_actor_id")) == business_id
        )
    return (
        _as_int(row.get("business_id")) == business_id
        or _as_int(row.get("provider_user_id")) == owner_user_id
    )


def _order_is_service(row):
    return (
        str(row.get("order_type") or "") in SERVICE_ORDER_TYPES
        or str(row.get("kind") or "") == "service"
    )


def _order_is_active(row):
    return str(row.get("status") or "new") not in TERMINAL_ORDER_STATUSES


def _recent_order_activity(orders):
    rows = sorted(orders, key=lambda row: _as_int(row.get("created_at")), reverse=True)[
        :5
    ]
    return [
        {
            "id": _as_int(row.get("id")),
            "kind": "service" if _order_is_service(row) else "order",
            "title": str(row.get("title") or row.get("item_name") or "Buyurtma"),
            "status": str(row.get("status") or "new"),
            "amount": _as_int(
                row.get("total_amount") or row.get("line_total") or row.get("amount")
            ),
            "created_at": _as_int(row.get("created_at")),
        }
        for row in rows
    ]


def _row_matches_business(row, business_id, owner_user_id):
    for key in ("business_id", "provider_actor_id", "actor_id"):
        if key in row and _as_int(row.get(key)) == business_id:
            return True
    return bool(owner_user_id and _as_int(row.get("user_id")) == owner_user_id)
