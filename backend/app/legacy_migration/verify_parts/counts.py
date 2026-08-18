"""Manba va nishon jadvallaridagi qatorlarni sanash."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.advertisements.model import Advertisement
from app.catalog.model import CatalogItem
from app.legacy_migration.model import (
    LegacyIdMap,
)
from app.listings.model import Listing
from app.stories.model import Story


async def _count_for_run(session, model, run_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count(model.id)).where(model.migration_run_id == run_id)
        )
        or 0
    )


async def _count_story_children_for_run(session, model, run_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count(model.id))
            .join(Story, Story.id == model.story_id)
            .where(Story.migration_run_id == run_id)
        )
        or 0
    )


async def _broken_mappings(
    session: AsyncSession,
    entity_types: tuple[str, ...],
    run_id: int,
) -> int:
    mappings = (
        await session.scalars(
            select(LegacyIdMap).where(
                LegacyIdMap.entity_type.in_(entity_types),
                LegacyIdMap.last_run_id == run_id,
                LegacyIdMap.target_id.is_not(None),
            )
        )
    ).all()
    models = {
        "catalog_item": CatalogItem,
        "listing": Listing,
        "advertisement": Advertisement,
        "story": Story,
    }
    broken = 0
    for mapping in mappings:
        model = models.get(mapping.entity_type)
        if model is None:
            continue
        if await session.get(model, mapping.target_id) is None:
            broken += 1
    return broken


def _source_media_references(source) -> int:
    total = 0
    queries = (
        "SELECT COUNT(*) FROM items WHERE TRIM(COALESCE(photo_file, '')) != ''",
        "SELECT COUNT(*) FROM listing_media WHERE TRIM(COALESCE(tg_file_id, '')) != ''",
        "SELECT COUNT(*) FROM advertisements "
        "WHERE TRIM(COALESCE(image_file, '')) != ''",
        "SELECT COUNT(*) FROM advertisements "
        "WHERE TRIM(COALESCE(mobile_image_file, '')) != ''",
        "SELECT COUNT(*) FROM stories WHERE TRIM(COALESCE(media_filename, '')) != ''",
        "SELECT COUNT(*) FROM stories "
        "WHERE TRIM(COALESCE(thumbnail_filename, '')) != ''",
        "SELECT COUNT(*) FROM messages "
        "WHERE media_type = 'photo' "
        "AND TRIM(COALESCE(media_url, '')) != ''",
    )
    for query in queries:
        try:
            total += int(source.execute(query).fetchone()[0])
        except Exception:
            continue
    return total


def _safe_source_count(source, table: str) -> int:
    try:
        return int(source.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    except Exception:
        return 0
