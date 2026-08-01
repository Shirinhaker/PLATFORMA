from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.legacy_migration.model import ReviewState
from app.listings.model import Listing, ListingMedia


LISTING_RESOURCES = frozenset({"listings"})


async def sync_business_listings(
    session: AsyncSession,
    *,
    account_id: int,
    payload: dict[str, Any],
    changed_resources: set[str],
) -> None:
    if not LISTING_RESOURCES.intersection(changed_resources):
        return

    rows = _rows(payload)
    existing = list((await session.scalars(
        select(Listing).where(
            Listing.owner_business_account_id == account_id,
            Listing.source_record_key.is_not(None),
        )
    )).all())
    by_source = {
        str(listing.source_record_key): listing
        for listing in existing
        if listing.source_record_key is not None
    }
    active_keys: set[str] = set()

    for ordinal, row in enumerate(rows):
        source_key = _source_key(row, ordinal)
        active_keys.add(source_key)
        listing = by_source.get(source_key)
        created_at = _record_time(row.get("created_at"))
        if listing is None:
            listing = Listing(
                owner_user_account_id=None,
                owner_business_account_id=account_id,
                source_record_key=source_key,
                category="boshqa",
                title="",
                price_text="",
                description="",
                address="",
                latitude=None,
                longitude=None,
                visibility="all",
                status="active",
                review_state=ReviewState.REVIEW_REQUIRED,
                migration_run_id=None,
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(listing)
            by_source[source_key] = listing
        _apply_listing(listing, row)
        await session.flush()
        await _replace_media(session, listing, row)

    for listing in existing:
        if str(listing.source_record_key) not in active_keys:
            await session.delete(listing)
    await session.flush()


def _apply_listing(listing: Listing, row: dict[str, Any]) -> None:
    category = _text(row.get("cat") or row.get("category"), 160) or "boshqa"
    title = _text(row.get("title") or row.get("name"), 200)
    listing.category = category
    listing.title = title
    listing.price_text = _text(row.get("price") or row.get("price_text"), 120)
    listing.description = _text(row.get("descr") or row.get("description"), 4000)
    listing.address = _text(row.get("address"), 300)
    listing.latitude = _number(row.get("lat", row.get("latitude")))
    listing.longitude = _number(row.get("lng", row.get("longitude")))
    listing.visibility = "own" if row.get("visibility") == "own" else "all"
    listing.status = "inactive" if row.get("status") == "inactive" else "active"
    listing.review_state = (
        ReviewState.READY
        if title and category in {"uy", "ish", "moshina", "hayvon", "texnika", "boshqa"}
        else ReviewState.REVIEW_REQUIRED
    )
    listing.updated_at = _record_time(row.get("updated_at"))


async def _replace_media(
    session: AsyncSession,
    listing: Listing,
    row: dict[str, Any],
) -> None:
    current = list((await session.scalars(
        select(ListingMedia).where(ListingMedia.listing_id == listing.id)
    )).all())
    for media in current:
        await session.delete(media)
    await session.flush()
    media_rows = row.get("media") if isinstance(row.get("media"), list) else []
    for position, media in enumerate(media_rows[:10]):
        if not isinstance(media, dict):
            continue
        object_key = _text(
            media.get("object_key") or media.get("file_id") or media.get("media_url"),
            1024,
        )
        if not object_key:
            continue
        session.add(ListingMedia(
            listing_id=listing.id,
            media_type="video" if media.get("type") == "video" else "photo",
            object_key=object_key,
            position=position,
            migration_state="copied",
            migration_run_id=None,
        ))
    await session.flush()


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    value = payload.get("listings") if isinstance(payload, dict) else None
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _source_key(row: dict[str, Any], ordinal: int) -> str:
    raw = str(row.get("id") if row.get("id") is not None else f"ordinal:{ordinal}")
    if len(raw) <= 160:
        return raw
    return f"{raw[:119]}:{hashlib.sha256(raw.encode()).hexdigest()[:40]}"


def _text(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _number(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result


def _record_time(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        raw = float(value)
    except (TypeError, ValueError, OverflowError):
        return datetime.now(UTC)
    return datetime.fromtimestamp(raw, tz=UTC)
