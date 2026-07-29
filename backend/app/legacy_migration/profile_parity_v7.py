from __future__ import annotations

from collections import defaultdict
import sqlite3
from typing import Any, Iterable

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
SENSITIVE_KEYS = {
    "pass_hash",
    "pass_plain",
    "password",
    "password_hash",
    "biz_pass_hash",
    "token",
    "token_hash",
    "start_token",
    "start_token_hash",
    "code_hash",
    "otp",
    "otp_hash",
    "secret",
    "private_key",
}
SENSITIVE_SUFFIXES = (
    "_password",
    "_secret",
    "_token",
)
_DROP = object()

# v1656da to‘g‘ridan-to‘g‘ri business_id bilan bog‘langan haqiqiy jadvallar.
BUSINESS_MODULE_TABLES = (
    "advertisements",
    "business_subscriptions",
    "staff",
    "staff_attendance",
    "staff_professions",
    "documents",
    "contractors",
    "stock_moves",
    "production_batches",
    "stock_batches",
    "item_recipes",
    "expenses",
    "expense_cats",
    "sales",
    "dining_places",
    "dining_bookings",
    "education_groups",
    "education_students",
    "education_student_group_history",
    "education_attendance",
    "education_payments",
    "education_teachers",
    "education_exams",
    "education_exam_results",
    "education_enrollments",
    "education_teacher_payments",
    "medical_doctor_services",
    "medical_doctors",
    "medical_queue",
    "medical_queue_history",
    # Eski snapshotlarda uchrashi mumkin bo‘lgan avvalgi nomlar.
    "business_reviews",
    "business_staff",
    "employees",
    "business_documents",
    "incoming_documents",
    "outgoing_documents",
    "internal_documents",
    "counterparties",
    "dining_orders",
    "warehouse_items",
    "warehouse_tx",
    "cash_transactions",
    "cash_register_transactions",
    "medical_queues",
    "medical_appointments",
)

USER_MODULE_TABLES = (
    "specialist_credentials",
    "specialist_offers",
    "specialist_portfolio",
    "push_preferences",
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
    users = _real_rows(_rows(source, "users"))
    orders = _real_rows(_rows(source, "orders"))
    order_items = _group_rows(
        _real_rows(_rows(source, "order_items")),
        "order_id",
    )
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
    story_views = _group_rows(
        _real_rows(_rows(source, "story_views")),
        "story_id",
    )
    story_reports = _group_rows(
        _real_rows(_rows(source, "story_reports")),
        "story_id",
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
    drivers = _real_rows(_rows(source, "drivers"))
    rides = _real_rows(_rows(source, "rides"))
    reviews = _real_rows(_rows(source, "reviews"))
    user_modules = {
        table: _real_rows(_rows(source, table))
        for table in USER_MODULE_TABLES
    }

    for user in users:
        legacy_id = _integer(user.get("id"))
        mapping = await _find_mapping(session, "user_account", legacy_id)
        if mapping is None or mapping.target_id is None:
            continue
        profile = await session.get(UserProfile, mapping.target_id)
        if profile is None:
            continue

        payload = _clean_payload(profile.cabinet_payload)
        user_orders = [
            row for row in orders
            if _order_belongs_to_user(row, legacy_id)
        ]
        user_listings = [
            row for row in listings
            if _integer(row.get("user_id")) == legacy_id
            and not _integer(row.get("business_id"))
        ]
        user_stories = [
            row for row in stories
            if str(row.get("owner_type") or "") == "user"
            and _integer(row.get("owner_id")) == legacy_id
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
        reviews_given = [
            row for row in reviews
            if _integer(row.get("reviewer_user_id")) == legacy_id
        ]
        reviews_received = [
            row for row in reviews
            if str(row.get("target_kind") or "") in {"user", "specialist"}
            and _integer(row.get("target_id")) == legacy_id
        ]

        payload.update(
            {
                "orders": _enrich_orders(
                    user_orders,
                    order_items,
                    order_messages,
                ),
                "listings": _enrich_listings(user_listings, listing_media),
                "stories": _enrich_stories(
                    user_stories,
                    story_views,
                    story_reports,
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
                "reviews_given": _safe_rows(reviews_given),
                "reviews_received": _safe_rows(reviews_received),
            }
        )
        for table, rows in user_modules.items():
            matched = [
                row for row in rows
                if _integer(row.get("user_id")) == legacy_id
            ]
            if matched or table in payload:
                payload[table] = _safe_rows(matched)

        profile.cabinet_payload = payload


async def enrich_business_cabinets(
    session: AsyncSession,
    source: sqlite3.Connection,
) -> None:
    businesses = _real_rows(_rows(source, "businesses"))
    orders = _real_rows(_rows(source, "orders"))
    order_items = _group_rows(
        _real_rows(_rows(source, "order_items")),
        "order_id",
    )
    order_messages = _group_rows(
        _real_rows(_rows(source, "order_messages")),
        "order_id",
    )
    item_groups = _real_rows(_rows(source, "item_groups"))
    items = _real_rows(_rows(source, "items"))
    listings = _real_rows(_rows(source, "listings"))
    listing_media = _group_rows(
        _real_rows(_rows(source, "listing_media")),
        "listing_id",
    )
    stories = _real_rows(_rows(source, "stories"))
    story_views = _group_rows(
        _real_rows(_rows(source, "story_views")),
        "story_id",
    )
    story_reports = _group_rows(
        _real_rows(_rows(source, "story_reports")),
        "story_id",
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
    reviews = _real_rows(_rows(source, "reviews"))
    qarz_rows = _real_rows(_rows(source, "qarz_tx"))
    production_inputs = _group_rows(
        _real_rows(_rows(source, "production_inputs")),
        "batch_id",
    )
    stock_consumptions = _group_rows(
        _real_rows(_rows(source, "stock_batch_consumptions")),
        "batch_id",
    )
    dining_items = _group_rows(
        _real_rows(_rows(source, "dining_booking_items")),
        "booking_id",
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
        business_groups = [
            row for row in item_groups
            if _integer(row.get("business_id")) == legacy_id
        ]
        business_items = [
            row for row in items
            if _integer(row.get("business_id")) == legacy_id
        ]
        business_listings = [
            row for row in listings
            if _integer(row.get("business_id")) == legacy_id
        ]
        business_stories = [
            row for row in stories
            if str(row.get("owner_type") or "") == "business"
            and _integer(row.get("owner_id")) == legacy_id
        ]
        business_payments = [
            row for row in payment_requests
            if str(row.get("actor_type") or "") == "business"
            and _integer(row.get("business_id")) == legacy_id
        ]
        business_reviews = [
            row for row in reviews
            if str(row.get("target_kind") or "") == "business"
            and _integer(row.get("target_id")) == legacy_id
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
                "item_groups": _safe_rows(business_groups),
                "items": _safe_rows(business_items),
                "listings": _enrich_listings(
                    business_listings,
                    listing_media,
                ),
                "stories": _enrich_stories(
                    business_stories,
                    story_views,
                    story_reports,
                ),
                "payment_requests": enriched_payments,
                "subscription_payments": enriched_payments,
                "reviews": _safe_rows(business_reviews),
                "business_reviews": _safe_rows(business_reviews),
            }
        )

        for table, rows in module_rows.items():
            if table == "payment_requests":
                continue
            matched = [
                row for row in rows
                if _row_belongs_to_business(row, legacy_id, owner_user_id)
            ]
            if table == "production_batches":
                payload[table] = _attach_children(
                    matched,
                    production_inputs,
                    "inputs",
                )
            elif table == "stock_batches":
                payload[table] = _attach_children(
                    matched,
                    stock_consumptions,
                    "consumptions",
                )
            elif table == "dining_bookings":
                payload[table] = _attach_children(
                    matched,
                    dining_items,
                    "items",
                )
            elif matched or table in payload:
                payload[table] = _safe_rows(matched)

        debtors = payload.get("debtors")
        debtor_ids = {
            _integer(row.get("id"))
            for row in debtors
            if isinstance(row, dict)
        } if isinstance(debtors, list) else set()
        payload["qarz_transactions"] = _safe_rows(
            row for row in qarz_rows
            if _integer(row.get("debtor_id")) in debtor_ids
        )

        documents = payload.get("documents")
        if isinstance(documents, list):
            payload["incoming_documents"] = _filter_documents(
                documents,
                "incoming",
            )
            payload["outgoing_documents"] = _filter_documents(
                documents,
                "outgoing",
            )
            payload["internal_documents"] = _filter_documents(
                documents,
                "internal",
            )
        contractors = payload.get("contractors")
        if isinstance(contractors, list):
            payload["counterparties"] = contractors
        stock_moves = payload.get("stock_moves")
        if isinstance(stock_moves, list):
            payload["warehouse_tx"] = stock_moves
        if business_items:
            payload["warehouse_items"] = _safe_rows(business_items)
        dining_bookings = payload.get("dining_bookings")
        if isinstance(dining_bookings, list):
            payload["dining_orders"] = dining_bookings
        medical_queue = payload.get("medical_queue")
        if isinstance(medical_queue, list):
            payload["medical_queues"] = medical_queue
            payload["medical_appointments"] = medical_queue

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


def _enrich_stories(
    rows: list[dict[str, object]],
    views_by_story: dict[int, list[dict[str, object]]],
    reports_by_story: dict[int, list[dict[str, object]]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source_row in rows:
        row = _safe_row(source_row)
        story_id = _integer(source_row.get("id"))
        row["views"] = _safe_rows(views_by_story.get(story_id, []))
        row["reports"] = _safe_rows(reports_by_story.get(story_id, []))
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


def _attach_children(
    rows: Iterable[dict[str, object]],
    children_by_parent: dict[int, list[dict[str, object]]],
    child_key: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source_row in rows:
        row = _safe_row(source_row)
        row[child_key] = _safe_rows(
            children_by_parent.get(_integer(source_row.get("id")), [])
        )
        result.append(row)
    return result


def _filter_documents(rows: list[object], wanted: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        direction = str(row.get("direction") or "").strip().casefold()
        if wanted == "incoming" and (
            "incoming" in direction
            or "kirim" in direction
            or "kiruvchi" in direction
        ):
            result.append(row)
        elif wanted == "outgoing" and (
            "outgoing" in direction
            or "chiq" in direction
            or "chiquvchi" in direction
        ):
            result.append(row)
        elif wanted == "internal" and (
            "internal" in direction
            or "ichki" in direction
        ):
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
    if "target_kind" in row and str(row.get("target_kind") or "") == "business":
        return _integer(row.get("target_id")) == business_id
    for key in (
        "business_id",
        "provider_actor_id",
        "sender_business_id",
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
    return any(
        _truthy(row.get(key))
        for key in EXPLICIT_DEMO_FLAGS
        if key in row
    )


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "demo",
        "test",
    }


def _clean_payload(value: object) -> dict[str, Any]:
    sanitized = _safe_value(value)
    return sanitized if isinstance(sanitized, dict) else {}


def _safe_rows(rows: Iterable[object]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or _is_explicit_demo(row):
            continue
        sanitized = _safe_value(row)
        if isinstance(sanitized, dict):
            result.append(sanitized)
    return result


def _safe_row(row: dict[str, object]) -> dict[str, Any]:
    sanitized = _safe_value(row)
    return sanitized if isinstance(sanitized, dict) else {}


def _safe_value(value: object) -> Any:
    if isinstance(value, dict):
        if _is_explicit_demo(value):
            return _DROP
        result: dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            if _is_sensitive_key(text_key):
                continue
            sanitized = _safe_value(item)
            if sanitized is not _DROP:
                result[text_key] = sanitized
        return result
    if isinstance(value, (list, tuple)):
        result: list[Any] = []
        for item in value:
            sanitized = _safe_value(item)
            if sanitized is not _DROP:
                result.append(sanitized)
        return result
    if isinstance(value, bytes):
        return {
            "binary_omitted": True,
            "size_bytes": len(value),
        }
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.casefold()
    return (
        normalized in SENSITIVE_KEYS
        or normalized.endswith("pass_hash")
        or normalized.endswith("password_hash")
        or normalized.endswith("token_hash")
        or normalized.endswith("code_hash")
        or any(normalized.endswith(suffix) for suffix in SENSITIVE_SUFFIXES)
    )


def _integer(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
