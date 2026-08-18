"""Mediani R2 ga ko'chirish va natijani belgilash."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.advertisements.model import Advertisement
from app.catalog.model import CatalogItem
from app.core.config import Settings
from app.legacy_migration.catalog_stage import ensure_media_mapping
from app.legacy_migration.media.constants import (
    CONTENT_TYPE_SUFFIXES,
    ResolvedMedia,
)
from app.legacy_migration.media.resolvers import (
    LocalMediaResolver,
    TelegramMediaResolver,
    _media_roots,
    _resolver_for_reference,
)
from app.legacy_migration.model import (
    LegacyIdMap,
    MediaMigration,
    MediaMigrationState,
    MigrationRun,
)
from app.legacy_migration.reconcile_parts.constants import StageResult
from app.listings.model import ListingMedia
from app.media.storage import R2Storage
from app.messages.model import Message
from app.stories.model import Story


async def migrate_media(
    session: AsyncSession,
    source: sqlite3.Connection,
    storage: R2Storage,
    settings: Settings,
    run: MigrationRun,
    *,
    local_resolver=None,
    telegram_resolver=None,
) -> StageResult:
    local = local_resolver or LocalMediaResolver(
        _media_roots(settings.legacy_media_roots),
        max_bytes=settings.legacy_media_max_bytes,
    )
    telegram = telegram_resolver or TelegramMediaResolver(
        settings.telegram_bot_token,
        max_bytes=settings.legacy_media_max_bytes,
    )
    await _ensure_message_media_mappings(session, source, run)
    counters = {"created": 0, "reused": 0, "updated": 0}
    records = (
        await session.scalars(
            select(MediaMigration)
            .where(MediaMigration.migration_run_id == run.id)
            .order_by(MediaMigration.id)
        )
    ).all()
    for record in records:
        if record.state is MediaMigrationState.COPIED:
            verified = storage.verify_object(
                record.destination_object_key,
                expected_size=record.size_bytes,
                expected_sha256=record.sha256,
                expected_content_type=record.content_type,
            )
            if verified:
                await _set_target_object_key(
                    session,
                    record,
                    record.destination_object_key,
                )
                counters["reused"] += 1
                continue
            record.attempts += 1
            record.updated_at = datetime.now(UTC)
            _mark_failure(
                record,
                MediaMigrationState.FAILED,
                "media.r2_verification_failed",
            )
            await _mark_story_media_failure(
                session, run, record, "story.media_verification_failed"
            )
            counters["updated"] += 1
            continue
        record.attempts += 1
        record.updated_at = datetime.now(UTC)
        reference = _source_reference(source, record)
        if not reference:
            _mark_failure(record, MediaMigrationState.MISSING, "media.missing")
            await _mark_story_media_failure(session, run, record, "story.media_missing")
            continue
        resolver = _resolver_for_reference(
            record,
            reference,
            local=local,
            telegram=telegram,
        )
        resolution = await resolver.resolve(reference)
        if resolution.media is None:
            state = (
                MediaMigrationState.MISSING
                if resolution.code == "media.missing"
                else MediaMigrationState.INVALID
                if resolution.code
                in {"media.path_outside_roots", "media.too_large", "media.invalid_type"}
                else MediaMigrationState.FAILED
            )
            _mark_failure(record, state, resolution.code)
            await _mark_story_media_failure(session, run, record, "story.media_missing")
            continue
        await _copy_media(session, storage, run, record, resolution.media)
        if record.state is MediaMigrationState.COPIED:
            counters["created"] += 1
        else:
            counters["updated"] += 1
    await session.flush()
    return StageResult(**counters)


async def _copy_media(
    session: AsyncSession,
    storage: R2Storage,
    run: MigrationRun,
    record: MediaMigration,
    media: ResolvedMedia,
) -> None:
    stored = storage.put_migration_object(
        stream=media.stream,
        run_id=run.id,
        entity_type=record.entity_type,
        legacy_id=record.legacy_id,
        slot=record.slot,
        sha256=media.sha256,
        content_type=media.content_type,
        size_bytes=media.size_bytes,
        suffix=CONTENT_TYPE_SUFFIXES[media.content_type],
    )
    verified = storage.verify_object(
        stored.object_key,
        expected_size=media.size_bytes,
        expected_sha256=media.sha256,
        expected_content_type=media.content_type,
    )
    if not verified:
        _mark_failure(
            record,
            MediaMigrationState.FAILED,
            "media.r2_verification_failed",
        )
        await _mark_story_media_failure(
            session, run, record, "story.media_verification_failed"
        )
        return
    record.destination_object_key = stored.object_key
    record.sha256 = media.sha256
    record.content_type = media.content_type
    record.size_bytes = media.size_bytes
    record.state = MediaMigrationState.COPIED
    record.last_error_code = ""
    await _set_target_object_key(session, record, stored.object_key)


def _mark_failure(
    record: MediaMigration,
    state: MediaMigrationState,
    code: str,
) -> None:
    record.state = state
    record.last_error_code = code


async def _set_target_object_key(
    session: AsyncSession,
    record: MediaMigration,
    object_key: str,
) -> None:
    if record.entity_type == "message":
        target = (
            await session.scalars(
                select(Message).where(Message.legacy_source_id == record.legacy_id)
            )
        ).one_or_none()
        if target is not None:
            target.media_object_key = object_key
        return
    mapping = (
        await session.scalars(
            select(LegacyIdMap).where(
                LegacyIdMap.entity_type == record.entity_type,
                LegacyIdMap.legacy_id == record.legacy_id,
            )
        )
    ).one_or_none()
    if mapping is None or mapping.target_id is None:
        return
    if record.entity_type == "catalog_item":
        target = await session.get(CatalogItem, mapping.target_id)
        if target is not None:
            target.image_object_key = object_key
    elif record.entity_type == "listing_media":
        target = await session.get(ListingMedia, mapping.target_id)
        if target is not None:
            target.object_key = object_key
            target.migration_state = "copied"
    elif record.entity_type == "advertisement":
        target = await session.get(Advertisement, mapping.target_id)
        if target is not None:
            field = (
                "mobile_image_object_key"
                if record.slot == "mobile"
                else "desktop_image_object_key"
            )
            setattr(target, field, object_key)
    elif record.entity_type == "story":
        target = await session.get(Story, mapping.target_id)
        if target is not None:
            if record.slot == "thumbnail":
                target.thumbnail_object_key = object_key
            else:
                target.media_object_key = object_key
                if target.media_type == "image":
                    target.thumbnail_object_key = object_key
            if (
                target.media_object_key
                and (target.media_type == "image" or target.thumbnail_object_key)
                and target.deleted_at is None
                and target.status != "failed"
            ):
                target.status = "active"


def _source_reference(
    source: sqlite3.Connection,
    record: MediaMigration,
) -> str:
    table, column = {
        ("catalog_item", "primary"): ("items", "photo_file"),
        ("listing_media", "primary"): ("listing_media", "tg_file_id"),
        ("advertisement", "desktop"): ("advertisements", "image_file"),
        ("advertisement", "mobile"): (
            "advertisements",
            "mobile_image_file",
        ),
        ("story", "primary"): ("stories", "media_filename"),
        ("story", "thumbnail"): ("stories", "thumbnail_filename"),
        ("message", "primary"): ("messages", "media_url"),
    }.get((record.entity_type, record.slot), ("", ""))
    if not table:
        return ""
    try:
        row = source.execute(
            f"SELECT {column} FROM {table} WHERE id = ?",
            (record.legacy_id,),
        ).fetchone()
    except sqlite3.Error:
        return ""
    if row is None:
        return ""
    value = row[0]
    return str(value).strip() if value is not None else ""


async def _ensure_message_media_mappings(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> None:
    """Eski umumiy chat rasmlarini shu media bosqichida R2 ga tayyorlaydi."""
    try:
        rows = source.execute(
            """SELECT id, media_url FROM messages
               WHERE media_type = 'photo'
                 AND TRIM(COALESCE(media_url, '')) != ''"""
        ).fetchall()
    except sqlite3.Error:
        return
    for row in rows:
        try:
            legacy_id = int(row[0])
        except (TypeError, ValueError):
            continue
        await ensure_media_mapping(
            session,
            run=run,
            entity_type="message",
            legacy_id=legacy_id,
            slot="primary",
            source_reference=str(row[1] or "").strip(),
        )


async def _mark_story_media_failure(
    session: AsyncSession,
    run: MigrationRun,
    record: MediaMigration,
    issue_code: str,
) -> None:
    if record.entity_type != "story":
        return
    mapping = await session.scalar(
        select(LegacyIdMap).where(
            LegacyIdMap.entity_type == "story",
            LegacyIdMap.legacy_id == record.legacy_id,
        )
    )
    if mapping is not None:
        mapping.mapping_status = "quarantined"
        mapping.review_reason = issue_code
        if mapping.target_id is not None:
            story = await session.get(Story, mapping.target_id)
            if story is not None:
                story.status = "failed"
    from app.legacy_migration.reconcile_parts.mapping import _ensure_issue

    await _ensure_issue(
        session,
        run,
        entity_type="story",
        legacy_id=record.legacy_id,
        issue_code=issue_code,
    )
