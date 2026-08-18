"""Darvozalar: ko'chirish to'liq bo'lganini baholash."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.advertisements.model import Advertisement
from app.catalog.model import CatalogItem
from app.legacy_migration.model import (
    LegacyIdMap,
    MediaMigration,
    MediaMigrationState,
    MigrationIssue,
    MigrationRun,
)
from app.legacy_migration.source import inventory_source
from app.legacy_migration.verify_parts.cabinet import (
    _cabinet_payload_violations,
)
from app.legacy_migration.verify_parts.constants import (
    GateResult,
    VerificationInput,
    VerificationReport,
)
from app.legacy_migration.verify_parts.counts import (
    _broken_mappings,
    _count_for_run,
    _count_story_children_for_run,
    _safe_source_count,
    _source_media_references,
)
from app.legacy_migration.verify_parts.helpers import (
    _equal,
    _zero,
)
from app.listings.model import Listing
from app.stories.model import Story, StoryReport, StoryView


def evaluate_gates(values: VerificationInput) -> VerificationReport:
    terminal_media = values.media_copied + values.media_missing + values.media_invalid
    gates = [
        _equal("mapping_coverage", values.mapped_rows, values.source_rows),
        _equal(
            "catalog_kind_count",
            values.target_catalog_kinds,
            values.source_catalog_kinds,
        ),
        _equal(
            "listing_count",
            values.target_listings,
            values.source_listings,
        ),
        _equal(
            "advertisement_count",
            values.target_advertisements,
            values.source_advertisements,
        ),
        _equal("story_count", values.target_stories, values.source_stories),
        _equal(
            "story_view_count",
            values.target_story_views,
            values.source_story_views,
        ),
        _equal(
            "story_report_count",
            values.target_story_reports,
            values.source_story_reports,
        ),
        _zero("broken_foreign_keys", values.broken_foreign_keys),
        _zero("identity_conflicts", values.identity_conflicts),
        _zero("cabinet_demo_rows", values.cabinet_demo_rows),
        _zero(
            "cabinet_sensitive_fields",
            values.cabinet_sensitive_fields,
        ),
        _zero("media_failed", values.media_failed),
        _equal(
            "media_terminal_count",
            terminal_media,
            values.source_media_references,
        ),
        _zero(
            "copied_media_verification",
            values.copied_media_unverified,
        ),
        _zero("idempotency", values.idempotency_created),
        GateResult(
            code="public_schema_leak",
            passed=not values.forbidden_public_fields,
            actual=list(values.forbidden_public_fields),
            expected=[],
        ),
    ]
    return VerificationReport(
        passed=all(gate.passed for gate in gates),
        gates=gates,
    )


async def verify_migration(
    session: AsyncSession,
    source,
    run: MigrationRun,
    *,
    forbidden_public_fields: tuple[str, ...] = (),
) -> VerificationReport:
    inventory = inventory_source(source)
    entity_types = (
        "user_account",
        "business_account",
        "catalog_group",
        "catalog_item",
        "listing",
        "listing_media",
        "advertisement",
        "story",
    )
    source_stories = _safe_source_count(source, "stories")
    source_story_views = _safe_source_count(source, "story_views")
    source_story_reports = _safe_source_count(source, "story_reports")
    source_rows = (
        sum(
            inventory[table]["total"]
            for table in (
                "users",
                "businesses",
                "item_groups",
                "items",
                "listings",
                "listing_media",
                "advertisements",
            )
        )
        + source_stories
    )
    mapped_rows = int(
        await session.scalar(
            select(func.count(LegacyIdMap.id)).where(
                LegacyIdMap.entity_type.in_(entity_types),
                LegacyIdMap.last_run_id == run.id,
            )
        )
        or 0
    )
    # Jami sanaladi, `migration_run_id` bo'yicha emas. Ilgari faqat shu
    # runda yaratilgan qatorlar sanalardi va `0007_catalog_live_sync`
    # backfilli yaratgan nusxalar (`migration_run_id IS NULL`) gate ko'zidan
    # yashirin qolardi: 3 ta xizmat bazada 6 ta qator bo'lsa ham gate 3/3
    # deb yashil chiqardi. Nishon baza migratsiya uchun toza yaratiladi,
    # shuning uchun undagi har bir qator manbadan kelgan bo'lishi shart.
    target_catalog = {
        str(kind): int(count)
        for kind, count in (
            await session.execute(
                select(CatalogItem.kind, func.count(CatalogItem.id)).group_by(
                    CatalogItem.kind
                )
            )
        ).all()
    }
    source_catalog = {
        kind: int(inventory["items"].get(kind, 0)) for kind in ("product", "service")
    }
    identity_conflicts = int(
        await session.scalar(
            select(func.count(MigrationIssue.id)).where(
                MigrationIssue.migration_run_id == run.id,
                MigrationIssue.resolved.is_(False),
                MigrationIssue.issue_code.like("identity.%"),
            )
        )
        or 0
    )
    media_counts = {
        state: int(count)
        for state, count in (
            await session.execute(
                select(
                    MediaMigration.state,
                    func.count(MediaMigration.id),
                )
                .where(MediaMigration.migration_run_id == run.id)
                .group_by(MediaMigration.state)
            )
        ).all()
    }
    copied_unverified = int(
        await session.scalar(
            select(func.count(MediaMigration.id)).where(
                MediaMigration.migration_run_id == run.id,
                MediaMigration.state == MediaMigrationState.COPIED,
                (
                    (MediaMigration.destination_object_key == "")
                    | (MediaMigration.sha256 == "")
                    | (MediaMigration.content_type == "")
                    | (MediaMigration.size_bytes <= 0)
                ),
            )
        )
        or 0
    )
    cabinet_demo_rows, cabinet_sensitive_fields = await _cabinet_payload_violations(
        session, run.id
    )
    values = VerificationInput(
        source_rows=source_rows,
        mapped_rows=mapped_rows,
        source_catalog_kinds=source_catalog,
        target_catalog_kinds={
            kind: target_catalog.get(kind, 0) for kind in ("product", "service")
        },
        source_listings=inventory["listings"]["total"],
        target_listings=await _count_for_run(session, Listing, run.id),
        source_advertisements=inventory["advertisements"]["total"],
        target_advertisements=await _count_for_run(
            session,
            Advertisement,
            run.id,
        ),
        broken_foreign_keys=await _broken_mappings(
            session,
            entity_types,
            run.id,
        ),
        identity_conflicts=identity_conflicts,
        source_media_references=_source_media_references(source),
        media_copied=media_counts.get(MediaMigrationState.COPIED, 0),
        media_missing=media_counts.get(MediaMigrationState.MISSING, 0),
        media_invalid=media_counts.get(MediaMigrationState.INVALID, 0),
        media_failed=media_counts.get(MediaMigrationState.FAILED, 0),
        copied_media_unverified=copied_unverified,
        idempotency_created=int(run.counters_json.get("idempotency_created", 0)),
        forbidden_public_fields=forbidden_public_fields,
        cabinet_demo_rows=cabinet_demo_rows,
        cabinet_sensitive_fields=cabinet_sensitive_fields,
        source_stories=source_stories,
        target_stories=(
            await _count_for_run(session, Story, run.id) if source_stories else 0
        ),
        source_story_views=source_story_views,
        target_story_views=(
            await _count_story_children_for_run(session, StoryView, run.id)
            if source_story_views
            else 0
        ),
        source_story_reports=source_story_reports,
        target_story_reports=(
            await _count_story_children_for_run(session, StoryReport, run.id)
            if source_story_reports
            else 0
        ),
    )
    return evaluate_gates(values)
