from __future__ import annotations

import sqlite3

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.legacy_migration.model import MigrationRun
from app.legacy_migration.reconcile import (
    StageResult,
    _ensure_issue,
    _find_mapping,
    _optional_int,
)
from app.payments.model import BusinessSubscription, PaymentRequest

PAID_PLANS = frozenset({"plus", "pro"})
SUBSCRIPTION_STATUSES = frozenset({"active", "superseded", "expired"})


async def import_business_subscriptions(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    """Import legacy Plus/Pro history after the typed table exists.

    Demo identities have already been removed from the temporary source by
    ``demo_prune``.  The legacy ``is_demo`` field is deliberately retained:
    for a remaining real business it records the activation method and does
    not revoke the entitlement.
    """
    if not _table_exists(source, "business_subscriptions"):
        return StageResult()

    counters = {
        "created": 0,
        "reused": 0,
        "updated": 0,
        "quarantined": 0,
        "issues": 0,
    }
    for row in _rows(source, "business_subscriptions"):
        legacy_id = _optional_int(row.get("id"))
        legacy_business_id = _optional_int(row.get("business_id"))
        plan_code = str(row.get("plan_code") or "").strip().casefold()
        if plan_code == "free":
            # Free remains a virtual fallback in the typed payment domain.
            continue

        duration_months = _optional_int(row.get("duration_months"))
        starts_at = _optional_int(row.get("starts_at"))
        expires_at = _optional_int(row.get("expires_at"))
        created_at = _optional_int(row.get("created_at"))
        status = str(row.get("status") or "").strip().casefold()
        valid = (
            legacy_id is not None
            and legacy_business_id is not None
            and plan_code in PAID_PLANS
            and duration_months is not None
            and duration_months > 0
            and starts_at is not None
            and starts_at > 0
            and expires_at is not None
            and expires_at > 0
            and created_at is not None
            and created_at > 0
            and status in SUBSCRIPTION_STATUSES
        )
        if not valid:
            counters["quarantined"] += 1
            counters["issues"] += await _ensure_issue(
                session,
                run,
                entity_type="business_subscription",
                legacy_id=legacy_id or 0,
                issue_code="business_subscription.invalid_source_row",
            )
            continue

        mapping = await _find_mapping(
            session,
            "business_account",
            legacy_business_id,
        )
        if mapping is None or mapping.target_id is None:
            counters["quarantined"] += 1
            counters["issues"] += await _ensure_issue(
                session,
                run,
                entity_type="business_subscription",
                legacy_id=legacy_id,
                issue_code="business_subscription.business_unresolved",
            )
            continue

        payment_request_id = await _payment_request_id(
            session,
            _optional_int(row.get("payment_request_id")),
        )
        values = {
            "business_account_id": int(mapping.target_id),
            "plan_code": plan_code,
            "duration_months": duration_months,
            "starts_at": starts_at,
            "expires_at": expires_at,
            "status": status,
            "is_demo": _truthy(row.get("is_demo")),
            "payment_request_id": payment_request_id,
            "created_at": created_at,
        }
        existing = await session.scalar(
            select(BusinessSubscription).where(
                BusinessSubscription.legacy_source_id == legacy_id
            )
        )
        if existing is None:
            session.add(
                BusinessSubscription(
                    legacy_source_id=legacy_id,
                    **values,
                )
            )
            counters["created"] += 1
            continue

        changed = any(
            getattr(existing, key) != value
            for key, value in values.items()
        )
        for key, value in values.items():
            setattr(existing, key, value)
        counters["updated" if changed else "reused"] += 1

    await session.flush()
    return StageResult(**counters)


async def _payment_request_id(
    session: AsyncSession,
    legacy_payment_request_id: int | None,
) -> int | None:
    if legacy_payment_request_id is None:
        return None
    return await session.scalar(
        select(PaymentRequest.id).where(
            PaymentRequest.legacy_source_id == legacy_payment_request_id
        )
    )


def _table_exists(source: sqlite3.Connection, table: str) -> bool:
    return source.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _rows(
    source: sqlite3.Connection,
    table: str,
) -> list[dict[str, object]]:
    cursor = source.execute(f'SELECT * FROM "{table}" ORDER BY id')
    columns = [item[0] for item in cursor.description or ()]
    return [
        dict(zip(columns, values, strict=True))
        for values in cursor.fetchall()
    ]


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }
