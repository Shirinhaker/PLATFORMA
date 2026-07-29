import hashlib
import sqlite3

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.model import CatalogGroup, CatalogItem
from app.legacy_migration.model import (
    MediaMigration,
    MediaMigrationState,
    MigrationRun,
    OwnerState,
    ReviewState,
)
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


VALID_KINDS = {"product", "service"}


async def import_catalog(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    groups = await import_catalog_groups(session, source, run)
    items = await import_catalog_items(session, source, run)
    return _combine(groups, items)


async def import_catalog_groups(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    business_names = _business_names(source)
    counters = _counters()
    for row in _source_rows(source, "item_groups"):
        legacy_id = int(row["id"])
        raw_kind = _text(row.get("kind"))
        name = _text(row.get("name"))
        issue_codes = []
        if not name:
            issue_codes.append("catalog_group.required.name")
        if raw_kind not in VALID_KINDS:
            issue_codes.append("catalog_group.required.kind")
        kind = raw_kind if raw_kind in VALID_KINDS else "product"
        review_state = (
            ReviewState.REVIEW_REQUIRED
            if issue_codes
            else ReviewState.READY
        )
        for code in issue_codes:
            counters["issues"] += await _ensure_issue(
                session,
                run,
                entity_type="catalog_group",
                legacy_id=legacy_id,
                issue_code=code,
            )

        business_id = _optional_int(row.get("business_id"))
        owner_id = await _mapped_target(
            session,
            "business_account",
            business_id,
        )
        values = {
            "business_account_id": owner_id,
            "owner_name_snapshot": business_names.get(business_id or 0, ""),
            "name": name,
            "kind": kind,
            "status": _text(row.get("status")) or "active",
            "review_state": review_state,
            "migration_run_id": run.id,
            "created_at": _unix_datetime(row.get("created_at")),
            "updated_at": _unix_datetime(row.get("created_at")),
        }
        await _upsert_catalog_target(
            session,
            model=CatalogGroup,
            entity_type="catalog_group",
            legacy_id=legacy_id,
            row=row,
            values=values,
            run=run,
            counters=counters,
        )
    await session.flush()
    return StageResult(**counters)


async def import_catalog_items(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    business_names = _business_names(source)
    counters = _counters()
    for row in _source_rows(source, "items"):
        legacy_id = int(row["id"])
        raw_kind = _text(row.get("kind"))
        name = _text(row.get("name"))
        issue_codes = []
        if not name:
            issue_codes.append("catalog.required.name")
        if raw_kind not in VALID_KINDS:
            issue_codes.append("catalog.required.kind")
        kind = raw_kind if raw_kind in VALID_KINDS else "product"
        review_state = (
            ReviewState.REVIEW_REQUIRED
            if issue_codes
            else ReviewState.READY
        )
        for code in issue_codes:
            counters["issues"] += await _ensure_issue(
                session,
                run,
                entity_type="catalog_item",
                legacy_id=legacy_id,
                issue_code=code,
            )

        business_id = _optional_int(row.get("business_id"))
        owner_id = await _mapped_target(
            session,
            "business_account",
            business_id,
        )
        group_id = await _mapped_target(
            session,
            "catalog_group",
            _optional_int(row.get("group_id")),
        )
        values = {
            "business_account_id": owner_id,
            "catalog_group_id": group_id,
            "owner_name_snapshot": business_names.get(business_id or 0, ""),
            "name": name,
            "price_text": _text(row.get("price")),
            "note": _text(row.get("note")),
            "kind": kind,
            "queue_enabled": bool(row.get("queue_enabled") or False),
            "image_object_key": "",
            "status": _text(row.get("status")) or "active",
            "owner_state": (
                OwnerState.LINKED if owner_id is not None else OwnerState.UNLINKED
            ),
            "review_state": review_state,
            "migration_run_id": run.id,
            "created_at": _unix_datetime(row.get("created_at")),
            "updated_at": _unix_datetime(row.get("created_at")),
        }
        await _upsert_catalog_target(
            session,
            model=CatalogItem,
            entity_type="catalog_item",
            legacy_id=legacy_id,
            row=row,
            values=values,
            run=run,
            counters=counters,
        )

        reference = _text(row.get("photo_file"))
        if reference:
            await ensure_media_mapping(
                session,
                run=run,
                entity_type="catalog_item",
                legacy_id=legacy_id,
                slot="primary",
                source_reference=reference,
            )
    await session.flush()
    return StageResult(**counters)


async def ensure_media_mapping(
    session: AsyncSession,
    *,
    run: MigrationRun,
    entity_type: str,
    legacy_id: int,
    slot: str,
    source_reference: str,
) -> MediaMigration:
    fingerprint = hashlib.sha256(
        source_reference.encode("utf-8")
    ).hexdigest()
    media = (
        await session.scalars(
            select(MediaMigration).where(
                MediaMigration.entity_type == entity_type,
                MediaMigration.legacy_id == legacy_id,
                MediaMigration.slot == slot,
            )
        )
    ).one_or_none()
    now = _unix_datetime(None)
    if media is None:
        media = MediaMigration(
            migration_run_id=run.id,
            entity_type=entity_type,
            legacy_id=legacy_id,
            slot=slot,
            source_reference_fingerprint=fingerprint,
            destination_object_key="",
            sha256="",
            content_type="",
            size_bytes=0,
            state=MediaMigrationState.PENDING,
            attempts=0,
            last_error_code="",
            created_at=now,
            updated_at=now,
        )
        session.add(media)
    elif media.source_reference_fingerprint != fingerprint:
        media.migration_run_id = run.id
        media.source_reference_fingerprint = fingerprint
        media.destination_object_key = ""
        media.sha256 = ""
        media.content_type = ""
        media.size_bytes = 0
        media.state = MediaMigrationState.PENDING
        media.attempts = 0
        media.last_error_code = ""
        media.updated_at = now
    await session.flush()
    return media


async def _upsert_catalog_target(
    session: AsyncSession,
    *,
    model,
    entity_type: str,
    legacy_id: int,
    row: dict[str, object],
    values: dict[str, object],
    run: MigrationRun,
    counters: dict[str, int],
) -> None:
    row_hash = source_row_hash(entity_type, row)
    mapping = await _find_mapping(session, entity_type, legacy_id)
    target = (
        await session.get(model, mapping.target_id)
        if mapping is not None and mapping.target_id is not None
        else None
    )
    if target is None:
        target = model(**values)
        session.add(target)
        await session.flush()
        counters["created"] += 1
    elif mapping is not None and mapping.source_row_hash == row_hash:
        counters["reused"] += 1
    else:
        for field, value in values.items():
            if field == "created_at":
                continue
            setattr(target, field, value)
        counters["updated"] += 1

    await _upsert_mapping(
        session,
        entity_type=entity_type,
        legacy_id=legacy_id,
        target_id=target.id,
        row_hash=row_hash,
        mapping_status="mapped",
        review_reason=(
            "review_required"
            if values["review_state"] is ReviewState.REVIEW_REQUIRED
            else ""
        ),
        run=run,
    )


async def _mapped_target(
    session: AsyncSession,
    entity_type: str,
    legacy_id: int | None,
) -> int | None:
    if legacy_id is None:
        return None
    mapping = await _find_mapping(session, entity_type, legacy_id)
    return mapping.target_id if mapping is not None else None


def _business_names(source: sqlite3.Connection) -> dict[int, str]:
    return {
        int(row["id"]): _text(row.get("name"))
        for row in _source_rows(source, "businesses")
    }


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
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


def _combine(*results: StageResult) -> StageResult:
    return StageResult(
        created=sum(result.created for result in results),
        reused=sum(result.reused for result in results),
        updated=sum(result.updated for result in results),
        quarantined=sum(result.quarantined for result in results),
        issues=sum(result.issues for result in results),
    )
