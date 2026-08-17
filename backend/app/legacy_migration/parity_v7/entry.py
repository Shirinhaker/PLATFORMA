"""Tashqaridan chaqiriladigan kirish nuqtalari."""

from __future__ import annotations

import sqlite3

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_assistant.legacy_import import import_ai_chat_history
from app.legacy_migration.business_subscription_stage import (
    import_business_subscriptions,
)
from app.legacy_migration.model import MigrationRun
from app.legacy_migration.parity_v7.enrich import (
    enrich_business_cabinets,
    enrich_user_cabinets,
)
from app.legacy_migration.parity_v7.helpers import (
    _target_tables_exist,
)
from app.legacy_migration.reconcile_parts.constants import StageResult
from app.legacy_migration.reconcile_v6_parts.entry import (
    reconcile_accounts as reconcile_accounts_v6,
)
from app.legacy_migration.reconcile_v6_parts.entry import (
    reconcile_businesses as reconcile_businesses_v6,
)
from app.taxi.legacy_import import import_taxi_domain


async def reconcile_accounts(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    result = await reconcile_accounts_v6(session, source, run)
    await enrich_user_cabinets(session, source)
    taxi_result = StageResult()
    if await _target_tables_exist(session, "taxi_drivers", "taxi_rides"):
        taxi_result = await import_taxi_domain(session, source, run)
    await session.flush()
    return StageResult(
        created=result.created + taxi_result.created,
        reused=result.reused + taxi_result.reused,
        updated=result.updated + taxi_result.updated,
        quarantined=result.quarantined + taxi_result.quarantined,
        issues=result.issues + taxi_result.issues,
    )


async def reconcile_businesses(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    result = await reconcile_businesses_v6(session, source, run)
    await enrich_business_cabinets(session, source)
    ai_result = StageResult()
    if await _target_tables_exist(session, "ai_chat_messages"):
        ai_result = await import_ai_chat_history(session, source, run)
    await session.flush()
    return StageResult(
        created=result.created + ai_result.created,
        reused=result.reused + ai_result.reused,
        updated=result.updated + ai_result.updated,
        quarantined=result.quarantined + ai_result.quarantined,
        issues=result.issues + ai_result.issues,
    )


async def import_late_typed_domains(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    """0005 bazaviy importidan keyin yaratiladigan typed domenlarni to'ldir."""
    required = (
        "ai_chat_messages",
        "business_subscriptions",
        "taxi_drivers",
        "taxi_rides",
    )
    if not await _target_tables_exist(session, *required):
        raise RuntimeError("late_typed_domain_tables_missing")

    ai_result = await import_ai_chat_history(session, source, run)
    subscription_result = await import_business_subscriptions(
        session,
        source,
        run,
    )
    taxi_result = await import_taxi_domain(session, source, run)
    await session.flush()
    return StageResult(
        created=(ai_result.created + subscription_result.created + taxi_result.created),
        reused=(ai_result.reused + subscription_result.reused + taxi_result.reused),
        updated=(ai_result.updated + subscription_result.updated + taxi_result.updated),
        quarantined=(
            ai_result.quarantined
            + subscription_result.quarantined
            + taxi_result.quarantined
        ),
        issues=(ai_result.issues + subscription_result.issues + taxi_result.issues),
    )
