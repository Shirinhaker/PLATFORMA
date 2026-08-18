"""Eski va yangi ID orasidagi moslik jadvali."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.legacy_migration.model import (
    LegacyIdMap,
    MigrationIssue,
    MigrationRun,
)


async def _find_mapping(
    session: AsyncSession,
    entity_type: str,
    legacy_id: int,
) -> LegacyIdMap | None:
    return (
        await session.scalars(
            select(LegacyIdMap).where(
                LegacyIdMap.entity_type == entity_type,
                LegacyIdMap.legacy_id == legacy_id,
            )
        )
    ).one_or_none()


async def _upsert_mapping(
    session: AsyncSession,
    *,
    entity_type: str,
    legacy_id: int,
    target_id: int | None,
    row_hash: str,
    mapping_status: str,
    review_reason: str,
    run: MigrationRun,
) -> LegacyIdMap:
    mapping = await _find_mapping(session, entity_type, legacy_id)
    if mapping is None:
        mapping = LegacyIdMap(
            entity_type=entity_type,
            legacy_id=legacy_id,
            target_id=target_id,
            source_row_hash=row_hash,
            mapping_status=mapping_status,
            review_reason=review_reason,
            last_run_id=run.id,
        )
        session.add(mapping)
    else:
        mapping.target_id = target_id
        mapping.source_row_hash = row_hash
        mapping.mapping_status = mapping_status
        mapping.review_reason = review_reason
        mapping.last_run_id = run.id
    await session.flush()
    return mapping


async def _ensure_issue(
    session: AsyncSession,
    run: MigrationRun,
    *,
    entity_type: str,
    legacy_id: int,
    issue_code: str,
) -> int:
    existing = (
        await session.scalars(
            select(MigrationIssue).where(
                MigrationIssue.migration_run_id == run.id,
                MigrationIssue.entity_type == entity_type,
                MigrationIssue.legacy_id == legacy_id,
                MigrationIssue.issue_code == issue_code,
            )
        )
    ).one_or_none()
    if existing is not None:
        return 0
    session.add(
        MigrationIssue(
            migration_run_id=run.id,
            entity_type=entity_type,
            legacy_id=legacy_id,
            issue_code=issue_code,
            details_json={},
            resolved=False,
            created_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return 1
