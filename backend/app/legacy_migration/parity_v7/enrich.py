"""Kabinet payloadini eski ma'lumot bilan to'ldirish."""

from __future__ import annotations

import sqlite3
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.legacy_migration.parity_v7.constants import (
    BUSINESS_MODULE_TABLES,
    USER_MODULE_TABLES,
)
from app.legacy_migration.parity_v7.helpers import (
    _clean_payload,
    _group_rows,
    _integer,
    _real_rows,
    _rows,
    _safe_row,
    _safe_rows,
    _safe_subscription_rows,
)
from app.legacy_migration.parity_v7.ownership import (
    _attach_children,
    _filter_documents,
    _order_belongs_to_business,
    _order_belongs_to_user,
    _row_belongs_to_business,
)
from app.legacy_migration.reconcile_parts.mapping import _find_mapping
from app.profiles.model import BusinessProfile, UserProfile


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
        table: _real_rows(_rows(source, table)) for table in USER_MODULE_TABLES
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
        user_orders = [row for row in orders if _order_belongs_to_user(row, legacy_id)]
        user_listings = [
            row
            for row in listings
            if _integer(row.get("user_id")) == legacy_id
            and not _integer(row.get("business_id"))
        ]
        user_stories = [
            row
            for row in stories
            if str(row.get("owner_type") or "") == "user"
            and _integer(row.get("owner_id")) == legacy_id
        ]
        user_payments = [
            row
            for row in payment_requests
            if _integer(row.get("user_id")) == legacy_id
            and str(row.get("actor_type") or "user") == "user"
        ]
        user_drivers = [
            row for row in drivers if _integer(row.get("user_id")) == legacy_id
        ]
        driver_ids = {_integer(row.get("id")) for row in user_drivers}
        reviews_given = [
            row for row in reviews if _integer(row.get("reviewer_user_id")) == legacy_id
        ]
        reviews_received = [
            row
            for row in reviews
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
                    row
                    for row in rides
                    if _integer(row.get("customer_id")) == legacy_id
                    or _integer(row.get("driver_id")) in driver_ids
                ),
                "reviews_given": _safe_rows(reviews_given),
                "reviews_received": _safe_rows(reviews_received),
            }
        )
        for table, rows in user_modules.items():
            matched = [row for row in rows if _integer(row.get("user_id")) == legacy_id]
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
        table: (
            _rows(source, table)
            if table == "business_subscriptions"
            else _real_rows(_rows(source, table))
        )
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
            row
            for row in orders
            if _order_belongs_to_business(row, legacy_id, owner_user_id)
        ]
        business_groups = [
            row for row in item_groups if _integer(row.get("business_id")) == legacy_id
        ]
        business_items = [
            row for row in items if _integer(row.get("business_id")) == legacy_id
        ]
        business_listings = [
            row for row in listings if _integer(row.get("business_id")) == legacy_id
        ]
        business_stories = [
            row
            for row in stories
            if str(row.get("owner_type") or "") == "business"
            and _integer(row.get("owner_id")) == legacy_id
        ]
        business_payments = [
            row
            for row in payment_requests
            if str(row.get("actor_type") or "") == "business"
            and _integer(row.get("business_id")) == legacy_id
        ]
        business_reviews = [
            row
            for row in reviews
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
                row
                for row in rows
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
            elif table == "business_subscriptions":
                if matched or table in payload:
                    payload[table] = _safe_subscription_rows(matched)
            elif matched or table in payload:
                payload[table] = _safe_rows(matched)

        debtors = payload.get("debtors")
        debtor_ids = (
            {_integer(row.get("id")) for row in debtors if isinstance(row, dict)}
            if isinstance(debtors, list)
            else set()
        )
        payload["qarz_transactions"] = _safe_rows(
            row for row in qarz_rows if _integer(row.get("debtor_id")) in debtor_ids
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
