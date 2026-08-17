"""Profil kabinetlarini to'ldirish."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.legacy_migration.reconcile_parts.mapping import _find_mapping
from app.legacy_migration.reconcile_parts.source import _source_rows
from app.legacy_migration.reconcile_v6_parts.helpers import (
    _as_float,
    _as_int,
    _json_safe,
    _optional_rows,
)
from app.legacy_migration.reconcile_v6_parts.ownership import (
    _order_belongs_to_business,
    _order_belongs_to_user,
    _order_is_active,
    _order_is_service,
    _recent_order_activity,
    _row_matches_business,
)
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile


async def _enrich_all_user_profiles(
    session: AsyncSession,
    source: sqlite3.Connection,
) -> None:
    businesses = _optional_rows(source, "businesses")
    businesses_by_owner: dict[int, list[dict[str, object]]] = {}
    for business in businesses:
        owner_id = _as_int(business.get("user_id"))
        businesses_by_owner.setdefault(owner_id, []).append(business)

    all_orders = _optional_rows(source, "orders")
    all_saved = _optional_rows(source, "saved")
    all_notifications = _optional_rows(source, "notifications")
    all_follows = _optional_rows(source, "follows")
    all_listings = _optional_rows(source, "listings")
    all_messages = _optional_rows(source, "messages")
    all_filters = _optional_rows(source, "notify_filters")
    all_specialists = _optional_rows(source, "specialists")

    for user in _source_rows(source, "users"):
        legacy_id = int(user["id"])
        mapping = await _find_mapping(session, "user_account", legacy_id)
        if mapping is None or mapping.target_id is None:
            continue
        profile = await session.get(UserProfile, mapping.target_id)
        if profile is None:
            continue

        owned_businesses = businesses_by_owner.get(legacy_id, [])
        orders = [row for row in all_orders if _order_belongs_to_user(row, legacy_id)]
        saved = [row for row in all_saved if _as_int(row.get("user_id")) == legacy_id]
        notifications = [
            row for row in all_notifications if _as_int(row.get("user_id")) == legacy_id
        ]
        following = [
            row for row in all_follows if _as_int(row.get("follower_id")) == legacy_id
        ]
        followers = [
            row
            for row in all_follows
            if str(row.get("target_kind") or "") == "user"
            and _as_int(row.get("target_id")) == legacy_id
        ]
        listings = [
            row for row in all_listings if _as_int(row.get("user_id")) == legacy_id
        ]
        messages = [
            row
            for row in all_messages
            if legacy_id
            in {
                _as_int(row.get("sender_id")),
                _as_int(row.get("receiver_id")),
                _as_int(row.get("sender_actor_id"))
                if str(row.get("sender_kind") or "user") == "user"
                else 0,
                _as_int(row.get("receiver_actor_id"))
                if str(row.get("receiver_kind") or "user") == "user"
                else 0,
            }
        ]
        filters = [
            row for row in all_filters if _as_int(row.get("user_id")) == legacy_id
        ]
        specialist = next(
            (
                row
                for row in all_specialists
                if _as_int(row.get("user_id")) == legacy_id
            ),
            {},
        )

        profile.followers_count = len(followers)
        profile.following_count = len(following)
        profile.has_business = bool(owned_businesses)
        profile.specialist_profile = _json_safe(specialist)
        profile.dashboard_snapshot = {
            "active_orders": sum(_order_is_active(row) for row in orders),
            "following": len(following),
            "saved": len(saved),
            "unread": sum(
                not bool(_as_int(row.get("is_read"))) for row in notifications
            ),
            "followers": len(followers),
        }
        profile.recent_activity = _recent_order_activity(orders)
        profile.cabinet_payload = {
            "orders": _json_safe(orders),
            "saved": _json_safe(saved),
            "notifications": _json_safe(notifications),
            "follows": _json_safe(following),
            "followers": _json_safe(followers),
            "listings": _json_safe(listings),
            "messages": _json_safe(messages),
            "notify_filters": _json_safe(filters),
            "specialist": _json_safe(specialist),
        }


async def _enrich_all_business_profiles(
    session: AsyncSession,
    source: sqlite3.Connection,
) -> None:
    users = {int(row["id"]): row for row in _source_rows(source, "users")}
    all_orders = _optional_rows(source, "orders")
    all_items = _optional_rows(source, "items")
    all_groups = _optional_rows(source, "item_groups")
    all_listings = _optional_rows(source, "listings")
    all_follows = _optional_rows(source, "follows")
    all_business_follows = _optional_rows(source, "business_follows")
    all_debtors = _optional_rows(source, "debtors")
    all_qarz = _optional_rows(source, "qarz_tx")
    all_messages = _optional_rows(source, "messages")
    all_notifications = _optional_rows(source, "notifications")

    optional_tables = {
        name: _optional_rows(source, name)
        for name in (
            "advertisements",
            "stories",
            "business_subscriptions",
            "subscription_payments",
            "business_reviews",
            "dining_places",
            "dining_orders",
            "warehouse_items",
            "warehouse_tx",
            "expenses",
            "sales",
            "education_groups",
            "education_students",
            "education_teachers",
        )
    }

    for business in _source_rows(source, "businesses"):
        legacy_id = int(business["id"])
        owner_legacy_id = _as_int(business.get("user_id"))
        mapping = await _find_mapping(session, "business_account", legacy_id)
        owner_mapping = await _find_mapping(
            session,
            "user_account",
            owner_legacy_id,
        )
        if mapping is None or mapping.target_id is None:
            continue
        profile = await session.get(BusinessProfile, mapping.target_id)
        if profile is None:
            continue

        orders = [
            row
            for row in all_orders
            if _order_belongs_to_business(row, legacy_id, owner_legacy_id)
        ]
        items = [
            row for row in all_items if _as_int(row.get("business_id")) == legacy_id
        ]
        groups = [
            row for row in all_groups if _as_int(row.get("business_id")) == legacy_id
        ]
        listings = [
            row for row in all_listings if _as_int(row.get("business_id")) == legacy_id
        ]
        followers = [
            row
            for row in all_follows
            if str(row.get("target_kind") or "") == "business"
            and _as_int(row.get("target_id")) == legacy_id
        ]
        following = [
            row
            for row in all_business_follows
            if _as_int(row.get("business_id")) == legacy_id
        ]
        debtors = [
            row for row in all_debtors if _as_int(row.get("business_id")) == legacy_id
        ]
        debtor_ids = {_as_int(row.get("id")) for row in debtors}
        qarz = [row for row in all_qarz if _as_int(row.get("debtor_id")) in debtor_ids]
        messages = [
            row
            for row in all_messages
            if (
                str(row.get("sender_kind") or "") == "business"
                and _as_int(row.get("sender_actor_id")) == legacy_id
            )
            or (
                str(row.get("receiver_kind") or "") == "business"
                and _as_int(row.get("receiver_actor_id")) == legacy_id
            )
        ]
        notifications = [
            row
            for row in all_notifications
            if _as_int(row.get("user_id")) == owner_legacy_id
            and str(row.get("actor_kind") or "") == "business"
            and _as_int(row.get("actor_id")) == legacy_id
        ]

        profile.followers_count = len(followers)
        profile.following_count = len(following)
        profile.rating_sum = _as_int(business.get("rating_sum"))
        profile.rating_count = _as_int(business.get("rating_cnt"))
        profile.map_visible = bool(_as_int(business.get("map_visible")))
        profile.dashboard_snapshot = _business_dashboard_snapshot(
            orders,
            debtors,
            qarz,
            items,
            followers,
            optional_tables,
            legacy_id,
        )
        profile.recent_activity = _recent_order_activity(orders)
        profile.cabinet_payload = {
            "orders": _json_safe(orders),
            "items": _json_safe(items),
            "item_groups": _json_safe(groups),
            "listings": _json_safe(listings),
            "followers": _json_safe(followers),
            "following": _json_safe(following),
            "debtors": _json_safe(debtors),
            "qarz_transactions": _json_safe(qarz),
            "messages": _json_safe(messages),
            "notifications": _json_safe(notifications),
            **{
                key: _json_safe(
                    [
                        row
                        for row in rows
                        if _row_matches_business(row, legacy_id, owner_legacy_id)
                    ]
                )
                for key, rows in optional_tables.items()
            },
        }

        if owner_mapping is not None and owner_mapping.target_id is not None:
            user_account = await session.get(Account, owner_mapping.target_id)
            business_account = await session.get(Account, mapping.target_id)
            if (
                user_account is not None
                and business_account is not None
                and user_account.account_type is AccountType.USER
                and business_account.account_type is AccountType.BUSINESS
            ):
                link = await session.get(ProfileLink, user_account.id)
                if link is None:
                    session.add(
                        ProfileLink(
                            user_account_id=user_account.id,
                            business_account_id=business_account.id,
                            created_at=datetime.now(UTC),
                        )
                    )
                else:
                    link.business_account_id = business_account.id
                user_profile = await session.get(UserProfile, user_account.id)
                if user_profile is not None:
                    user_profile.has_business = True


def _business_dashboard_snapshot(
    orders,
    debtors,
    qarz,
    items,
    followers,
    optional_tables,
    business_id,
):
    today_start = int(
        datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    )
    active = [row for row in orders if _order_is_active(row)]
    service = [row for row in orders if _order_is_service(row)]
    completed_today = sum(
        str(row.get("status") or "") in {"done", "delivered", "pickup_waiting_customer"}
        and _as_int(row.get("updated_at") or row.get("created_at")) >= today_start
        for row in orders
    )
    low_stock = sum(
        bool(_as_int(row.get("track_stock")))
        and _as_float(row.get("stock_qty")) <= _as_float(row.get("min_qty"))
        for row in items
    )
    debt_total = 0
    if qarz:
        for row in qarz:
            amount = max(0, _as_int(row.get("amount")))
            debt_total += -amount if str(row.get("type") or "") == "payment" else amount
    else:
        debt_total = sum(max(0, _as_int(row.get("balance"))) for row in debtors)
    expenses = sum(
        _as_int(row.get("amount"))
        for row in optional_tables.get("expenses", [])
        if _row_matches_business(row, business_id, 0)
        and _as_int(row.get("created_at")) >= today_start
    )
    sales = [
        row
        for row in optional_tables.get("sales", [])
        if _row_matches_business(row, business_id, 0)
        and _as_int(row.get("created_at")) >= today_start
    ]
    revenue = sum(
        _as_int(row.get("total") or row.get("amount") or row.get("line_total"))
        for row in sales
    )
    return {
        "revenue": revenue,
        "expenses": expenses,
        "sales_count": len(sales),
        "new_orders": sum(str(row.get("status") or "") == "new" for row in orders),
        "today_orders": sum(
            _as_int(row.get("created_at")) >= today_start for row in orders
        ),
        "active_orders": len(active),
        "pending_orders": sum(
            str(row.get("status") or "") in {"new", "accepted", "preparing"}
            for row in orders
        ),
        "accepted_orders": sum(
            str(row.get("status") or "") == "accepted" for row in orders
        ),
        "in_delivery": sum(
            str(row.get("status") or "")
            in {
                "courier_assigned",
                "courier_arrived_store",
                "handoff_waiting_seller",
                "in_delivery",
                "courier_arrived_customer",
                "delivered_waiting_customer",
            }
            for row in orders
        ),
        "completed_today": completed_today,
        "service_today": sum(
            _as_int(row.get("created_at")) >= today_start for row in service
        ),
        "service_active": sum(_order_is_active(row) for row in service),
        "debt_total": max(0, debt_total),
        "low_stock": low_stock,
        "items_count": len(items),
        "problem_orders": sum(bool(_as_int(row.get("problem_open"))) for row in orders),
        "followers": len(followers),
        "occupied_places": sum(
            bool(_as_int(row.get("occupied")))
            for row in optional_tables.get("dining_places", [])
            if _row_matches_business(row, business_id, 0)
        ),
        "groups": sum(
            _row_matches_business(row, business_id, 0)
            for row in optional_tables.get("education_groups", [])
        ),
        "students": sum(
            _row_matches_business(row, business_id, 0)
            for row in optional_tables.get("education_students", [])
        ),
        "today_lessons": 0,
        "deadlines": 0,
    }
