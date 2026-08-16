import sqlite3

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_assistant.model import AIChatMessage
from app.legacy_migration.model import MigrationRun
from app.legacy_migration.reconcile import (
    StageResult,
    _ensure_issue,
    _find_mapping,
    _optional_int,
    _unix_datetime,
)


async def import_ai_chat_history(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    if not _table_exists(source, "ai_chat_history"):
        return StageResult()

    counters = {
        "created": 0,
        "reused": 0,
        "updated": 0,
        "quarantined": 0,
        "issues": 0,
    }
    cursor = source.execute("SELECT * FROM ai_chat_history ORDER BY id")
    columns = [item[0] for item in cursor.description or ()]
    for values in cursor.fetchall():
        row = dict(zip(columns, values, strict=True))
        legacy_id = _optional_int(row.get("id"))
        legacy_business_id = _optional_int(row.get("business_id"))
        role = str(row.get("role") or "").strip()
        text = str(row.get("text") or "").strip()
        if legacy_id is None or role not in {"user", "assistant"} or not text:
            continue

        mapping = (
            await _find_mapping(session, "business_account", legacy_business_id)
            if legacy_business_id is not None
            else None
        )
        if mapping is None or mapping.target_id is None:
            counters["quarantined"] += 1
            counters["issues"] += await _ensure_issue(
                session,
                run,
                entity_type="ai_chat_message",
                legacy_id=legacy_id,
                issue_code="ai_chat_message.business_unresolved",
            )
            continue

        existing = (
            await session.scalars(
                select(AIChatMessage).where(
                    AIChatMessage.business_account_id == mapping.target_id,
                    AIChatMessage.legacy_source_id == legacy_id,
                )
            )
        ).one_or_none()
        created_at = _unix_datetime(row.get("created_at"))
        if existing is None:
            session.add(
                AIChatMessage(
                    business_account_id=mapping.target_id,
                    legacy_source_id=legacy_id,
                    role=role,
                    text=text,
                    source="legacy",
                    created_at=created_at,
                )
            )
            counters["created"] += 1
            continue

        changed = any(
            (
                existing.role != role,
                existing.text != text,
                existing.source != "legacy",
                existing.created_at != created_at,
            )
        )
        if changed:
            existing.role = role
            existing.text = text
            existing.source = "legacy"
            existing.created_at = created_at
            counters["updated"] += 1
        else:
            counters["reused"] += 1

    await session.flush()
    return StageResult(**counters)


def _table_exists(source: sqlite3.Connection, table: str) -> bool:
    return (
        source.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )
