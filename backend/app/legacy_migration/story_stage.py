from __future__ import annotations

from datetime import UTC, datetime
import sqlite3

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.legacy_migration.catalog_stage import ensure_media_mapping
from app.legacy_migration.model import MigrationRun
from app.legacy_migration.reconcile import (
    StageResult,
    _ensure_issue,
    _find_mapping,
    _source_rows,
    _text,
    _unix_datetime,
    _upsert_mapping,
    source_row_hash,
)
from app.stories.model import Story, StoryReport, StoryView


async def import_stories(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    counters = _counters()
    if not _table_exists(source, "stories"):
        return StageResult(**counters)
    for row in _source_rows(source, "stories"):
        legacy_id = int(row["id"])
        owner_type = _text(row.get("owner_type"))
        owner_entity = (
            "business_account" if owner_type == "business" else "user_account"
        )
        owner_id = await _mapped_target(
            session, owner_entity, _optional_int(row.get("owner_id"))
        )
        creator_id = await _mapped_target(
            session,
            "user_account",
            _optional_int(row.get("created_by_user_id")),
        )
        media_reference = _text(row.get("media_filename"))
        thumbnail_reference = _text(row.get("thumbnail_filename"))
        media_type = _text(row.get("media_type"))
        issues: list[str] = []
        if owner_type not in {"user", "business"} or owner_id is None:
            issues.append("story.owner_unresolved")
        if creator_id is None:
            issues.append("story.creator_unresolved")
        if not media_reference:
            issues.append("story.media_missing")
        if media_type == "video" and not thumbnail_reference:
            issues.append("story.media_missing")
        if media_type not in {"image", "video"}:
            issues.append("story.media_type_invalid")
        if len(_text(row.get("caption"))) > 200:
            issues.append("story.caption_invalid")
        for code in issues:
            counters["issues"] += await _ensure_issue(
                session,
                run,
                entity_type="story",
                legacy_id=legacy_id,
                issue_code=code,
            )

        row_hash = source_row_hash("story", row)
        mapping = await _find_mapping(session, "story", legacy_id)
        existing = (
            await session.get(Story, mapping.target_id)
            if mapping is not None and mapping.target_id is not None
            else None
        )
        if issues:
            if existing is not None:
                existing.status = "failed"
                existing.migration_run_id = run.id
            await _upsert_mapping(
                session,
                entity_type="story",
                legacy_id=legacy_id,
                target_id=existing.id if existing is not None else None,
                row_hash=row_hash,
                mapping_status="quarantined",
                review_reason=",".join(issues),
                run=run,
            )
            counters["quarantined"] += 1
            continue

        values = _story_values(row, owner_type, owner_id, creator_id, run.id)
        if existing is None:
            existing = Story(**values)
            session.add(existing)
            await session.flush()
            counters["created"] += 1
        elif mapping is not None and mapping.source_row_hash == row_hash:
            existing.migration_run_id = run.id
            counters["reused"] += 1
        else:
            for field, value in values.items():
                if field != "created_at":
                    setattr(existing, field, value)
            counters["updated"] += 1
        await _upsert_mapping(
            session,
            entity_type="story",
            legacy_id=legacy_id,
            target_id=existing.id,
            row_hash=row_hash,
            mapping_status="mapped",
            review_reason="",
            run=run,
        )
        await ensure_media_mapping(
            session,
            run=run,
            entity_type="story",
            legacy_id=legacy_id,
            slot="primary",
            source_reference=media_reference,
        )
        if media_type == "video" and thumbnail_reference:
            await ensure_media_mapping(
                session,
                run=run,
                entity_type="story",
                legacy_id=legacy_id,
                slot="thumbnail",
                source_reference=thumbnail_reference,
            )

    await _import_views(session, source, run, counters)
    await _import_reports(session, source, run, counters)
    await session.flush()
    return StageResult(**counters)


def _story_values(
    row: dict[str, object],
    owner_type: str,
    owner_id: int,
    creator_id: int,
    run_id: int,
) -> dict[str, object]:
    deleted_value = _optional_int(row.get("deleted_at")) or 0
    source_status = _text(row.get("status"))
    return {
        "owner_type": owner_type,
        "owner_account_id": owner_id,
        "created_by_account_id": creator_id,
        "created_by_staff_id": None,
        "media_type": _text(row.get("media_type")),
        "media_object_key": "",
        "thumbnail_object_key": "",
        "source_object_key": "",
        "mime_type": _text(row.get("mime_type")) or "application/octet-stream",
        "caption": _text(row.get("caption")),
        "duration_seconds": max(
            0.0, min(60.0, _optional_float(row.get("duration_seconds")) or 0.0)
        ),
        "status": "failed" if source_status == "failed" else "processing",
        "legacy_source_id": int(row["id"]),
        "migration_run_id": run_id,
        "created_at": _unix_datetime(row.get("created_at")),
        "expires_at": _unix_datetime(row.get("expires_at")),
        "deleted_at": (
            _unix_datetime(deleted_value) if deleted_value > 0 else None
        ),
    }


async def _import_views(session, source, run, counters) -> None:
    if not _table_exists(source, "story_views"):
        return
    cursor = source.execute(
        "SELECT * FROM story_views ORDER BY story_id, viewer_user_id"
    )
    columns = [item[0] for item in cursor.description or ()]
    for values in cursor.fetchall():
        row = dict(zip(columns, values, strict=True))
        story_id = await _mapped_target(
            session, "story", _optional_int(row.get("story_id"))
        )
        viewer_id = await _mapped_target(
            session, "user_account", _optional_int(row.get("viewer_user_id"))
        )
        if story_id is None or viewer_id is None:
            counters["issues"] += await _ensure_issue(
                session,
                run,
                entity_type="story_view",
                legacy_id=_optional_int(row.get("story_id")),
                issue_code="story_view.identity_unresolved",
            )
            counters["quarantined"] += 1
            continue
        existing = await session.scalar(
            select(StoryView).where(
                StoryView.story_id == story_id,
                StoryView.viewer_account_id == viewer_id,
            )
        )
        if existing is None:
            session.add(StoryView(
                story_id=story_id,
                viewer_account_id=viewer_id,
                viewed_at=_unix_datetime(row.get("viewed_at")),
            ))
            counters["created"] += 1
        else:
            counters["reused"] += 1


async def _import_reports(session, source, run, counters) -> None:
    if not _table_exists(source, "story_reports"):
        return
    for row in _source_rows(source, "story_reports"):
        legacy_id = int(row["id"])
        story_id = await _mapped_target(
            session, "story", _optional_int(row.get("story_id"))
        )
        reporter_id = await _mapped_target(
            session, "user_account", _optional_int(row.get("reporter_user_id"))
        )
        reason = _text(row.get("reason"))
        if story_id is None or reporter_id is None or not 10 <= len(reason) <= 300:
            counters["issues"] += await _ensure_issue(
                session,
                run,
                entity_type="story_report",
                legacy_id=legacy_id,
                issue_code="story_report.invalid_or_unresolved",
            )
            counters["quarantined"] += 1
            continue
        existing = await session.scalar(
            select(StoryReport).where(
                StoryReport.story_id == story_id,
                StoryReport.reporter_account_id == reporter_id,
            )
        )
        now = _unix_datetime(row.get("created_at"))
        status = _text(row.get("status"))
        normalized_status = (
            status if status in {"new", "reviewed", "dismissed"} else "new"
        )
        if existing is None:
            session.add(StoryReport(
                story_id=story_id,
                reporter_account_id=reporter_id,
                reason=reason,
                status=normalized_status,
                created_at=now,
                updated_at=now,
            ))
            counters["created"] += 1
        else:
            existing.reason = reason
            existing.status = normalized_status
            existing.updated_at = now
            counters["reused"] += 1


async def _mapped_target(
    session: AsyncSession,
    entity_type: str,
    legacy_id: int | None,
) -> int | None:
    if legacy_id is None:
        return None
    mapping = await _find_mapping(session, entity_type, legacy_id)
    return (
        int(mapping.target_id)
        if mapping is not None and mapping.target_id is not None
        else None
    )


def _table_exists(source: sqlite3.Connection, table: str) -> bool:
    return bool(source.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone())


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _counters() -> dict[str, int]:
    return {
        "created": 0,
        "reused": 0,
        "updated": 0,
        "quarantined": 0,
        "issues": 0,
    }
