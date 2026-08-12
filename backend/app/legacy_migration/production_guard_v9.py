from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.legacy_migration.model import (
    MediaMigration,
    MediaMigrationState,
    MigrationIssue,
)
from app.stories.model import Story


@dataclass(frozen=True)
class PromotionMediaGuardResult:
    copied: int
    expired_story_missing: int


def validate_promotion_media_rows(
    rows: Iterable[MediaMigration],
    stories_by_legacy_id: Mapping[int, Story],
    missing_story_issue_ids: set[int],
    *,
    run_id: int,
    now: datetime,
) -> PromotionMediaGuardResult:
    """Reject every unresolved media state except expired story evidence.

    Legacy stories can outlive their 24-hour visibility window in SQLite even
    after their local files have been removed.  Those records remain useful
    migration evidence, but they must be failed and non-public.  No active
    story or non-story media is allowed through this exception.
    """
    copied = 0
    expired_story_missing = 0
    for row in rows:
        if row.state is MediaMigrationState.COPIED:
            copied += 1
            continue
        if row.state is not MediaMigrationState.MISSING:
            raise RuntimeError(
                f"promotion_media_state_not_terminal:{row.id}:{row.state.value}"
            )
        if row.entity_type != "story":
            raise RuntimeError(
                f"promotion_non_story_media_missing:{row.entity_type}:{row.legacy_id}"
            )
        story = stories_by_legacy_id.get(int(row.legacy_id))
        if story is None:
            raise RuntimeError(
                f"promotion_missing_story_target_not_found:{row.legacy_id}"
            )
        if story.migration_run_id != run_id or story.status != "failed":
            raise RuntimeError(
                f"promotion_missing_story_not_failed:{row.legacy_id}"
            )
        expires_at = story.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        is_terminal = story.deleted_at is not None or expires_at <= now
        if not is_terminal:
            raise RuntimeError(
                f"promotion_active_story_media_missing:{row.legacy_id}"
            )
        if int(row.legacy_id) not in missing_story_issue_ids:
            raise RuntimeError(
                f"promotion_missing_story_issue_not_found:{row.legacy_id}"
            )
        expired_story_missing += 1
    return PromotionMediaGuardResult(
        copied=copied,
        expired_story_missing=expired_story_missing,
    )


async def validate_media_for_promotion(
    session: AsyncSession,
    run_id: int,
    *,
    now: datetime | None = None,
) -> PromotionMediaGuardResult:
    rows = list(
        (
            await session.scalars(
                select(MediaMigration)
                .where(MediaMigration.migration_run_id == run_id)
                .order_by(MediaMigration.id)
            )
        ).all()
    )
    missing_story_ids = {
        int(row.legacy_id)
        for row in rows
        if row.state is MediaMigrationState.MISSING
        and row.entity_type == "story"
    }
    stories_by_legacy_id: dict[int, Story] = {}
    missing_story_issue_ids: set[int] = set()
    if missing_story_ids:
        stories = list(
            (
                await session.scalars(
                    select(Story).where(
                        Story.legacy_source_id.in_(missing_story_ids)
                    )
                )
            ).all()
        )
        stories_by_legacy_id = {
            int(story.legacy_source_id): story
            for story in stories
            if story.legacy_source_id is not None
        }
        missing_story_issue_ids = {
            int(legacy_id)
            for legacy_id in (
                await session.scalars(
                    select(MigrationIssue.legacy_id).where(
                        MigrationIssue.migration_run_id == run_id,
                        MigrationIssue.entity_type == "story",
                        MigrationIssue.issue_code == "story.media_missing",
                        MigrationIssue.resolved.is_(False),
                        MigrationIssue.legacy_id.in_(missing_story_ids),
                    )
                )
            ).all()
            if legacy_id is not None
        }
    return validate_promotion_media_rows(
        rows,
        stories_by_legacy_id,
        missing_story_issue_ids,
        run_id=run_id,
        now=now or datetime.now(UTC),
    )
