from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.model import CatalogGroup, CatalogItem
from app.legacy_migration.model import OwnerState, ReviewState


CATALOG_RESOURCES = frozenset({"item_groups", "items"})


async def sync_business_catalog(
    session: AsyncSession,
    *,
    account_id: int,
    owner_name: str,
    payload: dict[str, Any],
    changed_resources: set[str],
) -> None:
    """Biznes kabinetidagi katalogni public katalog bilan bir tranzaksiyada tenglaydi."""
    if not CATALOG_RESOURCES.intersection(changed_resources):
        return

    normalized_owner = _text(owner_name, 160)
    group_rows = _rows(payload, "item_groups")
    item_rows = _rows(payload, "items")

    groups = list((await session.scalars(
        select(CatalogGroup).where(
            CatalogGroup.business_account_id == account_id,
            CatalogGroup.source_record_key.is_not(None),
        )
    )).all())
    groups_by_source = {
        str(group.source_record_key): group
        for group in groups
        if group.source_record_key is not None
    }
    active_group_keys: set[str] = set()

    for ordinal, row in enumerate(group_rows):
        source_key = _source_key(row, ordinal)
        active_group_keys.add(source_key)
        group = groups_by_source.get(source_key)
        created_at = _record_time(row.get("created_at"))
        if group is None:
            group = CatalogGroup(
                business_account_id=account_id,
                source_record_key=source_key,
                owner_name_snapshot=normalized_owner,
                name="",
                kind="product",
                status="active",
                review_state=ReviewState.REVIEW_REQUIRED,
                migration_run_id=None,
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(group)
            groups_by_source[source_key] = group
        _apply_group(group, row, normalized_owner)

    await session.flush()

    items = list((await session.scalars(
        select(CatalogItem).where(
            CatalogItem.business_account_id == account_id,
            CatalogItem.source_record_key.is_not(None),
        )
    )).all())
    items_by_source = {
        str(item.source_record_key): item
        for item in items
        if item.source_record_key is not None
    }
    active_item_keys: set[str] = set()

    for ordinal, row in enumerate(item_rows):
        source_key = _source_key(row, ordinal)
        active_item_keys.add(source_key)
        item = items_by_source.get(source_key)
        created_at = _record_time(row.get("created_at"))
        if item is None:
            item = CatalogItem(
                business_account_id=account_id,
                source_record_key=source_key,
                catalog_group_id=None,
                owner_name_snapshot=normalized_owner,
                name="",
                price_text="",
                note="",
                kind="product",
                queue_enabled=False,
                image_object_key="",
                status="active",
                owner_state=OwnerState.LINKED,
                review_state=ReviewState.REVIEW_REQUIRED,
                migration_run_id=None,
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(item)
            items_by_source[source_key] = item
        _apply_item(
            item,
            row,
            normalized_owner,
            groups_by_source,
        )

    await session.flush()

    for item in items:
        if str(item.source_record_key) not in active_item_keys:
            await session.delete(item)
    await session.flush()

    for group in groups:
        if str(group.source_record_key) not in active_group_keys:
            await session.delete(group)
    await session.flush()


def _apply_group(
    group: CatalogGroup,
    row: dict[str, Any],
    owner_name: str,
) -> None:
    kind, kind_valid = _kind(row)
    name = _text(row.get("name") or row.get("title"), 160)
    group.owner_name_snapshot = owner_name
    group.name = name
    group.kind = kind
    group.status = _text(row.get("status") or "active", 20) or "active"
    group.review_state = (
        ReviewState.READY
        if name and kind_valid
        else ReviewState.REVIEW_REQUIRED
    )
    group.updated_at = _record_time(row.get("updated_at"))


def _apply_item(
    item: CatalogItem,
    row: dict[str, Any],
    owner_name: str,
    groups_by_source: dict[str, CatalogGroup],
) -> None:
    kind, kind_valid = _kind(row)
    name = _text(row.get("name") or row.get("title"), 160)
    group_key = _optional_key(
        row.get("group_id", row.get("item_group_id", row.get("group")))
    )
    group = groups_by_source.get(group_key) if group_key is not None else None
    price = _first(row, "price", "price_text", "price_amount")
    note = _first(row, "note", "description", "descr")
    image_key = _first(row, "image_object_key", "photo_object_key")

    item.catalog_group_id = group.id if group is not None else None
    item.owner_name_snapshot = owner_name
    item.name = name
    item.price_text = _scalar_text(price, 120)
    item.note = _text(note, 2000)
    item.kind = kind
    item.queue_enabled = _boolean(row.get("queue_enabled"))
    if image_key not in (None, ""):
        item.image_object_key = _text(image_key, 1024)
    item.status = _text(row.get("status") or "active", 20) or "active"
    item.owner_state = OwnerState.LINKED
    item.review_state = (
        ReviewState.READY
        if name and kind_valid
        else ReviewState.REVIEW_REQUIRED
    )
    item.updated_at = _record_time(row.get("updated_at"))


def _rows(payload: dict[str, Any], resource: str) -> list[dict[str, Any]]:
    value = payload.get(resource) if isinstance(payload, dict) else None
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _source_key(row: dict[str, Any], ordinal: int) -> str:
    value = row.get("id")
    candidate = str(value if value is not None else f"ordinal:{ordinal}")
    if len(candidate) <= 160:
        return candidate
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:40]
    return f"{candidate[:119]}:{digest}"


def _optional_key(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _first(row: dict[str, Any], *names: str) -> object:
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return ""


def _kind(row: dict[str, Any]) -> tuple[str, bool]:
    raw = _text(
        row.get("kind") or row.get("item_type") or row.get("type"),
        20,
    ).casefold()
    normalized = "service" if raw == "service" else "product"
    return normalized, raw in {"", "product", "service"}


def _text(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _scalar_text(value: object, limit: int) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))[:limit]
    return _text(value, limit)


def _boolean(value: object) -> bool:
    return value is True or str(value or "").strip().casefold() in {
        "1",
        "true",
        "on",
        "yes",
    }


def _record_time(value: object) -> datetime:
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return datetime.now(UTC)
    try:
        return datetime.fromtimestamp(timestamp, UTC)
    except (OverflowError, OSError, ValueError):
        return datetime.now(UTC)
