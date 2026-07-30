from datetime import UTC, datetime
from math import isfinite
import sqlite3

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.legacy_migration.model import MigrationRun
from app.legacy_migration.reconcile import (
    StageResult,
    _account_record,
    _apply_account_record,
    _business_account_record,
    _business_profile_values,
    _ensure_user_profile,
    _find_mapping,
    _optional_int,
    _source_rows,
    _text,
    _unix_datetime,
    _upsert_mapping,
    reconcile_accounts as reconcile_accounts_v5,
    reconcile_businesses as reconcile_businesses_v5,
    source_row_hash,
)
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile


TERMINAL_ORDER_STATUSES = {
    "done",
    "delivered",
    "cancelled",
    "canceled",
    "rejected",
    "pickup_waiting_customer",
}
SERVICE_ORDER_TYPES = {"booking", "service", "queue", "medical"}


async def reconcile_accounts(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    pairs = await _shared_login_pairs(session, source)
    counters = _counters()

    for owner_id, business_id, occupied in pairs:
        user_row = _row_by_id(source, "users", owner_id)
        record = _account_record(user_row)
        existing = await _account_by_login_and_type(
            session,
            str(record["login"]),
            AccountType.USER,
        )
        created = existing is None
        if existing is None:
            created_at = _unix_datetime(record.get("created_at"))
            existing = Account(
                account_type=AccountType.USER,
                login=str(record["login"]),
                password_hash=str(record["password_hash"]),
                telegram_user_id=None,
                status=str(record["status"]),
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(existing)
            await session.flush()
        else:
            _apply_account_record(existing, record)

        counters["issues"] += await _ensure_user_profile(
            session,
            existing,
            record,
            run=run,
            legacy_id=owner_id,
        )
        await _upsert_mapping(
            session,
            entity_type="user_account",
            legacy_id=owner_id,
            target_id=existing.id,
            row_hash=source_row_hash("user_account", record),
            mapping_status="mapped",
            review_reason="",
            run=run,
        )
        counters["created" if created else "updated"] += 1

        business_mapping = await _find_mapping(
            session,
            "business_account",
            business_id,
        )
        if business_mapping is not None:
            business_mapping.target_id = occupied.id
            business_mapping.mapping_status = "mapped"
            business_mapping.review_reason = ""
            business_mapping.last_run_id = run.id

    filtered = _filtered_source(source, {pair[0] for pair in pairs}, set())
    try:
        ordinary = await reconcile_accounts_v5(session, filtered, run)
    finally:
        filtered.close()

    await _enrich_all_user_profiles(session, source)
    await session.flush()
    return _combine(StageResult(**counters), ordinary)


async def reconcile_businesses(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    pairs = await _shared_login_pairs(session, source)
    counters = _counters()

    for owner_id, business_id, occupied in pairs:
        user_row = _row_by_id(source, "users", owner_id)
        business_row = _row_by_id(source, "businesses", business_id)
        record = _business_account_record(business_row, user_row)
        record["login"] = _text(user_row.get("login")).casefold()
        record["password_hash"] = _text(user_row.get("pass_hash"))
        _apply_account_record(occupied, record)

        profile = await session.get(BusinessProfile, occupied.id)
        values = _business_profile_values(business_row)
        if profile is None:
            profile = BusinessProfile(account_id=occupied.id, **values)
            session.add(profile)
            counters["created"] += 1
        else:
            for field, value in values.items():
                setattr(profile, field, value)
            counters["updated"] += 1

        await _upsert_mapping(
            session,
            entity_type="business_account",
            legacy_id=business_id,
            target_id=occupied.id,
            row_hash=source_row_hash("business_account", record),
            mapping_status="mapped",
            review_reason="",
            run=run,
        )

    filtered = _filtered_source(source, set(), {pair[1] for pair in pairs})
    try:
        ordinary = await reconcile_businesses_v5(session, filtered, run)
    finally:
        filtered.close()

    await _enrich_all_business_profiles(session, source)
    await session.flush()
    return _combine(StageResult(**counters), ordinary)


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
        orders = [
            row for row in all_orders
            if _order_belongs_to_user(row, legacy_id)
        ]
        saved = [row for row in all_saved if _as_int(row.get("user_id")) == legacy_id]
        notifications = [
            row for row in all_notifications
            if _as_int(row.get("user_id")) == legacy_id
        ]
        following = [
            row for row in all_follows
            if _as_int(row.get("follower_id")) == legacy_id
        ]
        followers = [
            row for row in all_follows
            if str(row.get("target_kind") or "") == "user"
            and _as_int(row.get("target_id")) == legacy_id
        ]
        listings = [
            row for row in all_listings
            if _as_int(row.get("user_id")) == legacy_id
        ]
        messages = [
            row for row in all_messages
            if legacy_id in {
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
            row for row in all_filters
            if _as_int(row.get("user_id")) == legacy_id
        ]
        specialist = next(
            (
                row for row in all_specialists
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
            "unread": sum(not bool(_as_int(row.get("is_read"))) for row in notifications),
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
            row for row in all_orders
            if _order_belongs_to_business(row, legacy_id, owner_legacy_id)
        ]
        items = [row for row in all_items if _as_int(row.get("business_id")) == legacy_id]
        groups = [row for row in all_groups if _as_int(row.get("business_id")) == legacy_id]
        listings = [row for row in all_listings if _as_int(row.get("business_id")) == legacy_id]
        followers = [
            row for row in all_follows
            if str(row.get("target_kind") or "") == "business"
            and _as_int(row.get("target_id")) == legacy_id
        ]
        following = [
            row for row in all_business_follows
            if _as_int(row.get("business_id")) == legacy_id
        ]
        debtors = [row for row in all_debtors if _as_int(row.get("business_id")) == legacy_id]
        debtor_ids = {_as_int(row.get("id")) for row in debtors}
        qarz = [row for row in all_qarz if _as_int(row.get("debtor_id")) in debtor_ids]
        messages = [
            row for row in all_messages
            if (
                str(row.get("sender_kind") or "") == "business"
                and _as_int(row.get("sender_actor_id")) == legacy_id
            ) or (
                str(row.get("receiver_kind") or "") == "business"
                and _as_int(row.get("receiver_actor_id")) == legacy_id
            )
        ]
        notifications = [
            row for row in all_notifications
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
                key: _json_safe([
                    row for row in rows
                    if _row_matches_business(row, legacy_id, owner_legacy_id)
                ])
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
    today_start = int(datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
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
        row for row in optional_tables.get("sales", [])
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
        "today_orders": sum(_as_int(row.get("created_at")) >= today_start for row in orders),
        "active_orders": len(active),
        "pending_orders": sum(str(row.get("status") or "") in {"new", "accepted", "preparing"} for row in orders),
        "accepted_orders": sum(str(row.get("status") or "") == "accepted" for row in orders),
        "in_delivery": sum(str(row.get("status") or "") in {"courier_assigned", "courier_arrived_store", "handoff_waiting_seller", "in_delivery", "courier_arrived_customer", "delivered_waiting_customer"} for row in orders),
        "completed_today": completed_today,
        "service_today": sum(_as_int(row.get("created_at")) >= today_start for row in service),
        "service_active": sum(_order_is_active(row) for row in service),
        "debt_total": max(0, debt_total),
        "low_stock": low_stock,
        "items_count": len(items),
        "problem_orders": sum(bool(_as_int(row.get("problem_open"))) for row in orders),
        "followers": len(followers),
        "occupied_places": sum(bool(_as_int(row.get("occupied"))) for row in optional_tables.get("dining_places", []) if _row_matches_business(row, business_id, 0)),
        "groups": sum(_row_matches_business(row, business_id, 0) for row in optional_tables.get("education_groups", [])),
        "students": sum(_row_matches_business(row, business_id, 0) for row in optional_tables.get("education_students", [])),
        "today_lessons": 0,
        "deadlines": 0,
    }


async def _shared_login_pairs(
    session: AsyncSession,
    source: sqlite3.Connection,
) -> list[tuple[int, int, Account]]:
    businesses_by_owner: dict[int, list[dict[str, object]]] = {}
    for business in _source_rows(source, "businesses"):
        owner_id = _optional_int(business.get("user_id"))
        if owner_id is not None:
            businesses_by_owner.setdefault(owner_id, []).append(business)

    pairs: list[tuple[int, int, Account]] = []
    for user in _source_rows(source, "users"):
        owner_id = int(user["id"])
        businesses = businesses_by_owner.get(owner_id, [])
        if (
            len(businesses) != 1
            or _optional_int(user.get("tg_id")) is not None
            or _text(businesses[0].get("biz_login"))
            or not _text(user.get("login"))
        ):
            continue
        occupied = await _account_by_login_and_type(
            session,
            _text(user.get("login")).casefold(),
            AccountType.BUSINESS,
        )
        if occupied is None:
            continue
        if await session.get(BusinessProfile, occupied.id) is None:
            continue
        pairs.append((owner_id, int(businesses[0]["id"]), occupied))
    return pairs


async def _account_by_login_and_type(
    session: AsyncSession,
    login: str,
    account_type: AccountType,
) -> Account | None:
    return (
        await session.scalars(
            select(Account).where(
                func.lower(Account.login) == login,
                Account.account_type == account_type,
            )
        )
    ).one_or_none()


def _row_by_id(source: sqlite3.Connection, table: str, legacy_id: int) -> dict[str, object]:
    return next(row for row in _source_rows(source, table) if int(row["id"]) == legacy_id)


def _filtered_source(source, excluded_users, excluded_businesses):
    target = sqlite3.connect(":memory:")
    source.backup(target)
    if excluded_users:
        placeholders = ",".join("?" for _ in excluded_users)
        target.execute(f"DELETE FROM users WHERE id IN ({placeholders})", tuple(sorted(excluded_users)))
    if excluded_businesses:
        placeholders = ",".join("?" for _ in excluded_businesses)
        target.execute(f"DELETE FROM businesses WHERE id IN ({placeholders})", tuple(sorted(excluded_businesses)))
    target.commit()
    target.row_factory = sqlite3.Row
    return target


def _optional_rows(source: sqlite3.Connection, table: str) -> list[dict[str, object]]:
    exists = source.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    if not exists:
        return []
    try:
        return [dict(row) for row in source.execute(f'SELECT * FROM "{table}"').fetchall()]
    except sqlite3.DatabaseError:
        return []


def _order_belongs_to_user(row, user_id):
    if "customer_user_id" in row:
        return _as_int(row.get("customer_user_id")) == user_id and str(row.get("customer_kind") or "user") == "user"
    return _as_int(row.get("user_id") or row.get("customer_id")) == user_id


def _order_belongs_to_business(row, business_id, owner_user_id):
    if "provider_actor_id" in row:
        return str(row.get("provider_kind") or "business") == "business" and _as_int(row.get("provider_actor_id")) == business_id
    return _as_int(row.get("business_id")) == business_id or _as_int(row.get("provider_user_id")) == owner_user_id


def _order_is_service(row):
    return str(row.get("order_type") or "") in SERVICE_ORDER_TYPES or str(row.get("kind") or "") == "service"


def _order_is_active(row):
    return str(row.get("status") or "new") not in TERMINAL_ORDER_STATUSES


def _recent_order_activity(orders):
    rows = sorted(orders, key=lambda row: _as_int(row.get("created_at")), reverse=True)[:5]
    return [
        {
            "id": _as_int(row.get("id")),
            "kind": "service" if _order_is_service(row) else "order",
            "title": str(row.get("title") or row.get("item_name") or "Buyurtma"),
            "status": str(row.get("status") or "new"),
            "amount": _as_int(row.get("total_amount") or row.get("line_total") or row.get("amount")),
            "created_at": _as_int(row.get("created_at")),
        }
        for row in rows
    ]


def _row_matches_business(row, business_id, owner_user_id):
    for key in ("business_id", "provider_actor_id", "actor_id"):
        if key in row and _as_int(row.get(key)) == business_id:
            return True
    return bool(owner_user_id and _as_int(row.get("user_id")) == owner_user_id)


def _json_safe(value):
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, float):
        return value if isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value) -> float:
    try:
        parsed = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return parsed if isfinite(parsed) else 0.0


def _counters() -> dict[str, int]:
    return {"created": 0, "reused": 0, "updated": 0, "quarantined": 0, "issues": 0}


def _combine(first: StageResult, second: StageResult) -> StageResult:
    return StageResult(
        created=first.created + second.created,
        reused=first.reused + second.reused,
        updated=first.updated + second.updated,
        quarantined=first.quarantined + second.quarantined,
        issues=first.issues + second.issues,
    )
