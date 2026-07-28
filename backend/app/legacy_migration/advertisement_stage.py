from datetime import time
import json
import sqlite3

from sqlalchemy.ext.asyncio import AsyncSession

from app.advertisements.model import Advertisement
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


async def import_advertisements(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    counters = _counters()
    for row in _source_rows(source, "advertisements"):
        legacy_id = int(row["id"])
        issue_codes = []
        title = _text(row.get("title"))
        if not title:
            issue_codes.append("advertisement.required.title")

        targets, targets_valid = _parse_targets(row.get("targets_json"))
        if not targets_valid:
            issue_codes.append("advertisement.targets_invalid")
        daily_start = _parse_time(row.get("daily_start"))
        daily_end = _parse_time(row.get("daily_end"))
        if (
            not bool(row.get("daily_all_day") or False)
            and (daily_start is None or daily_end is None)
        ):
            issue_codes.append("advertisement.daily_time_invalid")

        for code in issue_codes:
            counters["issues"] += await _ensure_issue(
                session,
                run,
                entity_type="advertisement",
                legacy_id=legacy_id,
                issue_code=code,
            )

        owner_user_id = await _mapped_target(
            session,
            "user_account",
            _optional_int(row.get("user_id")),
        )
        owner_business_id = await _mapped_target(
            session,
            "business_account",
            _optional_int(row.get("business_id")),
        )
        created_at = _unix_datetime(row.get("created_at"))
        values = {
            "owner_user_account_id": owner_user_id,
            "owner_business_account_id": owner_business_id,
            "actor_type": _text(row.get("actor_type")) or "user",
            "title": title,
            "caption": _text(row.get("caption")),
            "desktop_image_object_key": "",
            "mobile_image_object_key": "",
            "crop_x": _float_or(row.get("crop_x"), 50.0),
            "crop_y": _float_or(row.get("crop_y"), 50.0),
            "crop_zoom": _float_or(row.get("crop_zoom"), 1.0),
            "daily_all_day": bool(row.get("daily_all_day") or False),
            "daily_start": daily_start,
            "daily_end": daily_end,
            "targets_json": targets,
            "placement": "home",
            "start_at": _unix_datetime(row.get("start_at")),
            "end_at": _unix_datetime(row.get("end_at")),
            "duration_days": _int_or(row.get("duration_days"), 0),
            "price": _int_or(row.get("price"), 0),
            "district_count": _int_or(row.get("district_count"), 0),
            "hours_per_day": _int_or(row.get("hours_per_day"), 0),
            "district_hour_rate": _int_or(
                row.get("district_hour_rate"),
                0,
            ),
            "billable_district_hours": _int_or(
                row.get("billable_district_hours"),
                0,
            ),
            "price_code": _text(row.get("price_code")),
            "status": _text(row.get("status")) or "active",
            "views": _int_or(row.get("views"), 0),
            "clicks": _int_or(row.get("clicks"), 0),
            "review_state": (
                ReviewState.REVIEW_REQUIRED
                if issue_codes
                else ReviewState.READY
            ),
            "migration_run_id": run.id,
            "created_at": created_at,
            "updated_at": _unix_datetime(row.get("updated_at")),
        }
        await _upsert_advertisement(
            session,
            legacy_id=legacy_id,
            row=row,
            values=values,
            run=run,
            counters=counters,
        )

        for slot, reference in (
            ("desktop", _text(row.get("image_file"))),
            ("mobile", _text(row.get("mobile_image_file"))),
        ):
            if reference:
                await ensure_media_mapping(
                    session,
                    run=run,
                    entity_type="advertisement",
                    legacy_id=legacy_id,
                    slot=slot,
                    source_reference=reference,
                )

    await session.flush()
    return StageResult(**counters)


async def _upsert_advertisement(
    session: AsyncSession,
    *,
    legacy_id: int,
    row: dict[str, object],
    values: dict[str, object],
    run: MigrationRun,
    counters: dict[str, int],
) -> Advertisement:
    row_hash = source_row_hash("advertisement", row)
    mapping = await _find_mapping(session, "advertisement", legacy_id)
    target = (
        await session.get(Advertisement, mapping.target_id)
        if mapping is not None and mapping.target_id is not None
        else None
    )
    if target is None:
        target = Advertisement(**values)
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
        entity_type="advertisement",
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
    return target


def _parse_targets(value: object) -> tuple[list[dict[str, str]], bool]:
    try:
        parsed = json.loads(_text(value) or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return [], False
    if not isinstance(parsed, list):
        return [], False

    targets: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            return [], False
        target = {}
        for field in ("region", "district"):
            content = _text(item.get(field))
            if content:
                target[field] = content
        if not target and item:
            return [], False
        targets.append(target)
    return targets, True


def _parse_time(value: object) -> time | None:
    text = _text(value)
    if not text:
        return None
    try:
        return time.fromisoformat(text)
    except ValueError:
        return None


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


def _int_or(value: object, default: int) -> int:
    parsed = _optional_int(value)
    return default if parsed is None else parsed


def _float_or(value: object, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _counters() -> dict[str, int]:
    return {
        "created": 0,
        "reused": 0,
        "updated": 0,
        "quarantined": 0,
        "issues": 0,
    }
