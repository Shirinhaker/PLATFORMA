import sqlite3

from sqlalchemy.ext.asyncio import AsyncSession

from app.legacy_migration.catalog_stage import ensure_media_mapping
from app.legacy_migration.model import MigrationRun, ReviewState
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
from app.listings.model import Listing, ListingMedia


async def import_listings(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    counters = _counters()
    for row in _source_rows(source, "listings"):
        legacy_id = int(row["id"])
        title = _text(row.get("title"))
        category = _text(row.get("cat"))
        issue_codes = []
        if not title:
            issue_codes.append("listing.required.title")
        if not category:
            issue_codes.append("listing.required.category")

        user_owner_id = await _mapped_target(
            session,
            "user_account",
            _optional_int(row.get("user_id")),
        )
        business_owner_id = await _mapped_target(
            session,
            "business_account",
            _optional_int(row.get("business_id")),
        )
        if user_owner_id is None:
            issue_codes.append("listing.owner_unresolved")
        for code in issue_codes:
            counters["issues"] += await _ensure_issue(
                session,
                run,
                entity_type="listing",
                legacy_id=legacy_id,
                issue_code=code,
            )

        created_at = _unix_datetime(row.get("created_at"))
        values = {
            "owner_user_account_id": user_owner_id,
            "owner_business_account_id": business_owner_id,
            "category": category,
            "title": title,
            "price_text": _text(row.get("price")),
            "description": _text(row.get("descr")),
            "address": _text(row.get("address")),
            "latitude": _optional_float(row.get("lat")),
            "longitude": _optional_float(row.get("lng")),
            "visibility": _text(row.get("visibility")) or "all",
            "status": _text(row.get("status")) or "active",
            "review_state": (
                ReviewState.REVIEW_REQUIRED
                if issue_codes
                else ReviewState.READY
            ),
            "migration_run_id": run.id,
            "created_at": created_at,
            "updated_at": created_at,
        }
        listing = await _upsert_target(
            session,
            model=Listing,
            entity_type="listing",
            legacy_id=legacy_id,
            row=row,
            values=values,
            run=run,
            counters=counters,
        )
        await _import_listing_media(
            session,
            source,
            run,
            legacy_listing_id=legacy_id,
            target_listing_id=listing.id,
            counters=counters,
        )

    await session.flush()
    return StageResult(**counters)


async def _import_listing_media(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
    *,
    legacy_listing_id: int,
    target_listing_id: int,
    counters: dict[str, int],
) -> None:
    rows = [
        row
        for row in _source_rows(source, "listing_media")
        if int(row.get("listing_id") or 0) == legacy_listing_id
    ]
    for row in rows:
        legacy_id = int(row["id"])
        raw_media_type = _text(row.get("mtype"))
        media_type = (
            raw_media_type
            if raw_media_type in {"photo", "video"}
            else "photo"
        )
        if raw_media_type not in {"photo", "video"}:
            counters["issues"] += await _ensure_issue(
                session,
                run,
                entity_type="listing_media",
                legacy_id=legacy_id,
                issue_code="listing_media.type_invalid",
            )
        values = {
            "listing_id": target_listing_id,
            "media_type": media_type,
            "object_key": "",
            "position": _optional_int(row.get("pos")) or 0,
            "migration_state": "pending",
            "migration_run_id": run.id,
        }
        await _upsert_target(
            session,
            model=ListingMedia,
            entity_type="listing_media",
            legacy_id=legacy_id,
            row=row,
            values=values,
            run=run,
            counters=counters,
        )
        reference = _text(row.get("tg_file_id"))
        if reference:
            await ensure_media_mapping(
                session,
                run=run,
                entity_type="listing_media",
                legacy_id=legacy_id,
                slot="primary",
                source_reference=reference,
            )


async def _upsert_target(
    session: AsyncSession,
    *,
    model,
    entity_type: str,
    legacy_id: int,
    row: dict[str, object],
    values: dict[str, object],
    run: MigrationRun,
    counters: dict[str, int],
):
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
            if values.get("review_state") is ReviewState.REVIEW_REQUIRED
            else ""
        ),
        run=run,
    )
    return target


async def _mapped_target(
    session: AsyncSession,
    entity_type: str,
    legacy_id: int | None,
) -> int | None:
    if legacy_id is None:
        return None
    mapping = await _find_mapping(session, entity_type, legacy_id)
    return mapping.target_id if mapping is not None else None


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
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
