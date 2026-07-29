from __future__ import annotations

from collections import defaultdict
import sqlite3
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.legacy_migration.model import MigrationRun
from app.legacy_migration.reconcile import StageResult, _find_mapping
from app.legacy_migration.reconcile_v6 import (
    reconcile_accounts as reconcile_accounts_v6,
    reconcile_businesses as reconcile_businesses_v6,
)
from app.profiles.model import BusinessProfile, UserProfile


EXPLICIT_DEMO_FLAGS = (
    "is_demo",
    "demo",
    "is_test",
    "test_mode",
    "demo_mode",
)
SENSITIVE_FIELD_PARTS = (
    "pass_hash",
    "password_hash",
    "token_hash",
    "start_token",
    "code_hash",
    "secret",
    "private_key",
    "content",
)

BUSINESS_MODULE_TABLES = (
    "advertisements",
    "stories",
    "business_subscriptions",
    "payment_requests",
    "business_reviews",
    "staff",
    "business_staff",
    "employees",
    "documents",
    "business_documents",
    "incoming_documents",
    "outgoing_documents",
    "internal_documents",
    "counterparties",
    "dining_places",
    "dining_orders",
    "warehouse_items",
    "warehouse_tx",
    "expenses",
    "sales",
    "cash_transactions",
    "cash_register_transactions",
    "education_groups",
    "education_students",
    "education_teachers",
    "medical_queues",
    "medical_appointments",
)


async def reconcile_accounts(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    result = await reconcile_accounts_v6(session, source, run)
    await enrich_user_cabinets(session, source)
    await session.flush()
    return result


async def reconcile_businesses(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    result = await reconcile_businesses_v6(session, source, run)
    await enrich_business_cabinets(session, source)
    await session.flush()
    return result


async def enrich_user_cabinets(
    session: AsyncSession,
    source: sqlite3.Connection,
) -> None:
    users = _rows(source, "users")
    orders = _real_rows(_rows(source, "orders"))
    order_items = _group_rows(_real_rows(_rows(source, "order_items")), "order_id")
    order_messages = _group_rows(
        _real_rows(_rows(source, "order_messages")),
        "order_id",
    )
    listings = _real_rows(_rows(source, "listings"))
    listing_media = _group_rows(
        _real_rows(_rows(source, "listing_media")),
        "listing_id",
    )
    stories = _real_rows(_rows(source, "stories"))
    payment_requests = _real_rows(_rows(source, "payment_requests"))
    payment_attempts = _group_rows(
        _real_rows(_rows(source, "payment_attempts")),
        "payment_request_id",
    )
    payment_events = _group_rows(
        _real_rows(_rows(source, "payment_events")),
        "payment_request_id",
    )
    drivers = _real_rows(_rows(source, "drivers"))
    rides = _real_rows(_rows(source, "rides"))

    for user in users:
        legacy_id = _integer(user.get("id"))
        mapping = await _find_mapping(session, "user_account", legacy_id)
        if mapping is None or mapping.target_id is None:
            continue
        profile = await session.get(UserProfile, mapping.target_id)
        if profile is None:
            continue

        payload = _clean_payload(profile.cabinet_payload)
        user_orders = [row for row in orders if _order_belongs_to_user(row, legacy_id)]
        user_listings = [
            row for row in listings
            if _integer(row.get("user_id")) == legacy_id
        ]
        user_payments = [
            row for row in payment_requests
            if _integer(row.get("user_id")) == legacy_id
            and str(row.get("actor_type") or "user") == "user"
        ]
        user_drivers = [
            row for row in drivers
            if _integer(row.get("user_id")) == legacy_id
        ]
        driver_ids = {_integer(row.get("id")) for row in user_drivers}

        payload.update(
            {
                "orders": _enrich_orders(
                    user_orders,
                    order_items,
                    order_messages,
                ),
                "listings": _enrich_listings(user_listings, listing_media),
                "stories": _safe_rows(
                    row for row in stories
                    if str(row.get("owner_type") or "") == "user"
                    and _integer(row.get("owner_id")) == legacy_id
                ),
                "payments": _enrich_payments(
                    user_payments,
                    payment_attempts,
                    payment_events,
                ),
                "drivers": _safe_rows(user_drivers),
                "rides": _safe_rows(
                    row for row in rides
                    if _integer(row.get("customer_id")) == legacy_id
                    or _integer(row.get("driver_id")) in driver_ids
                ),
            }
        )
        profile.cabinet_payload = payload


async def enrich_business_cabinets(
    session: AsyncSession,
    source: sqlite3.Connection,
) -> None:
    businesses = _rows(source, "businesses")
    orders = _real_rows(_rows(source, "orders"))
    order_items = _group_rows(_real_rows(_rows(source, "order_items")), "order_id")
    order_messages = _group_rows(
        _real_rows(_rows(source, "order_messages")),
        "order_id",
    )
    listings = _real_rows(_rows(source, "listings"))
    listing_media = _group_rows(
        _real_rows(_rows(source, "listing_media")),
        "listing_id",
    )
    payment_requests = _real_rows(_rows(source, "payment_requests"))
    payment_attempts = _group_rows(
        _real_rows(_rows(source, "payment_attempts")),
        "payment_request_id",
    )
    payment_events = _group_rows(
        _real_rows(_rows(source, "payment_events")),
        "payment_request_id",
    )
    module_rows = {
        table: _real_rows(_rows(source, table))
        for table in BUSINESS_MODULE_TABLES
    }

    for business in businesses:
        legacy_id = _integer(business.get("id"))
        owner_user_id = _integer(business.get("user_id"))
        mapping = await _find_mapping(session, "business_account", legacy_id)
        if mapping is None or mapping.target_id is None:
            continue
        profile = await session.get(BusinessProfile, mapping.target_id)
        if profile is None:
            continue

        payload = _clean_payload(profile.cabinet_payload)
        business_orders = [
            row for row in orders
            if _order_belongs_to_business(row, legacy_id, owner_user_id)
        ]
        business_listings = [
            row for row in listings
            if _integer(row.get("business_id")) == legacy_id
        ]
        business_payments = [
            row for row in payment_requests
            if str(row.get("actor_type") or "") == "business"
            and _integer(row.get("business_id")) == legacy_id
        ]
        enriched_payments = _enrich_payments(
            business_payments,
            payment_attempts,
            payment_events,
        )

        payload.update(
            {
                "orders": _enrich_orders(
                    business_orders,
                    order_items,
                    order_messages,
                ),
                "listings": _enrich_listings(
                    business_listings,
                    listing_media,
                ),
                "payment_requests": enriched_payments,
                # v1656 biznes kabinetidagi To‘lovlarim shu kalitdan o‘qiydi.
                "subscription_payments": enriched_payments,
            }
        )
        for table, rows in module_rows.items():
            if table == "payment_requests":
                continue
            matched = [
                row for row in rows
                if _row_belongs_to_business(row, legacy_id, owner_user_id)
            ]
            if matched or table in payload:
                payload[table] = _safe_rows(matched)

        profile.cabinet_payload = payload


def _enrich_orders(
    rows: list[dict[str, object]],
    items_by_order: dict[int, list[dict[str, object]]],
    messages_by_order: dict[int, list[dict[str, object]]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source_row in rows:
        row = _safe_row(source_row)
        order_id = _integer(source_row.get("id"))
        row["items"] = _safe_rows(items_by_order.get(order_id, []))
        row["messages"] = _safe_rows(messages_by_order.get(order_id, []))
        result.append(row)
    return result


def _enrich_listings(
    rows: list[dict[str, object]],
    media_by_listing: dict[int, list[dict[str, object]]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source_row in rows:
        row = _safe_row(source_row)
        row["media"] = _safe_rows(
            media_by_listing.get(_integer(source_row.get("id")), [])
        )
        result.append(row)
    return result


def _enrich_payments(
    rows: list[dict[str, object]],
    attempts_by_request: dict[int, list[dict[str, object]]],
    events_by_request: dict[int, list[dict[str, object]]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source_row in rows:
        row = _safe_row(source_row)
        request_id = _integer(source_row.get("id"))
        row["attempts"] = _safe_rows(attempts_by_request.get(request_id, []))
        row["events"] = _safe_rows(events_by_request.get(request_id, []))
        result.append(row)
    return result


def _order_belongs_to_user(row: dict[str, object], user_id: int) -> bool:
    if "customer_kind" in row and str(row.get("customer_kind") or "user") != "user":
        return False
    candidate = (
        row.get("customer_user_id")
        or row.get("customer_actor_id")
        or row.get("user_id")
        or row.get("customer_id")
    )
    return _integer(candidate) == user_id


def _order_belongs_to_business(
    row: dict[str, object],
    business_id: int,
    owner_user_id: int,
) -> bool:
    if "provider_kind" in row:
        if str(row.get("provider_kind") or "business") != "business":
            return False
        return _integer(row.get("provider_actor_id")) == business_id
    return (
        _integer(row.get("business_id")) == business_id
        or _integer(row.get("provider_user_id")) == owner_user_id
    )


def _row_belongs_to_business(
    row: dict[str, object],
    business_id: int,
    owner_user_id: int,
) -> bool:
    if "owner_type" in row and str(row.get("owner_type") or "") == "business":
        return _integer(row.get("owner_id")) == business_id
    if "actor_type" in row and str(row.get("actor_type") or "") == "business":
        return _integer(row.get("business_id") or row.get("actor_id")) == business_id
    for key in (
        "business_id",
        "provider_actor_id",
        "actor_id",
    ):
        if key in row and _integer(row.get(key)) == business_id:
            return True
    return bool(
        owner_user_id
        and "user_id" in row
        and _integer(row.get("user_id")) == owner_user_id
    )


def _rows(source: sqlite3.Connection, table: str) -> list[dict[str, object]]:
    exists = source.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    if not exists:
        return []
    try:
        return [
            dict(row)
            for row in source.execute(f'SELECT * FROM "{table}"').fetchall()
        ]
    except sqlite3.DatabaseError:
        return []


def _group_rows(
    rows: list[dict[str, object]],
    key: str,
) -> dict[int, list[dict[str, object]]]:
    grouped: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[_integer(row.get(key))].append(row)
    return grouped


def _real_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [row for row in rows if not _is_explicit_demo(row)]


def _is_explicit_demo(row: dict[str, object]) -> bool:
    return any(_truthy(row.get(key)) for key in EXPLICIT_DEMO_FLAGS if key in row)


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "demo", "test"}


def _clean_payload(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, list):
            result[str(key)] = _safe_rows(
                row for row in item
                if not isinstance(row, dict) or not _is_explicit_demo(row)
            )
        else:
            result[str(key)] = _safe_value(item)
    return result


def _safe_rows(rows) -> list[dict[str, Any]]:
    return [_safe_row(row) for row in rows if isinstance(row, dict)]


def _safe_row(row: dict[str, object]) -> dict[str, Any]:
    return {
        str(key): _safe_value(value)
        for key, value in row.items()
        if not _is_sensitive_key(str(key))
    }


def _safe_value(value: object) -> Any:
    if isinstance(value, dict):
        return _safe_row(value)
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.casefold()
    return any(part in normalized for part in SENSITIVE_FIELD_PARTS)


def _integer(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
