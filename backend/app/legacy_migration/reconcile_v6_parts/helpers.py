"""Tur o'girish va sanoqlarni birlashtirish."""

from __future__ import annotations

import sqlite3
from math import isfinite

from app.legacy_migration.reconcile_parts.constants import StageResult
from app.legacy_migration.reconcile_parts.source import _source_rows


def _row_by_id(
    source: sqlite3.Connection, table: str, legacy_id: int
) -> dict[str, object]:
    return next(
        row for row in _source_rows(source, table) if int(row["id"]) == legacy_id
    )


def _filtered_source(source, excluded_users, excluded_businesses):
    target = sqlite3.connect(":memory:")
    source.backup(target)
    if excluded_users:
        placeholders = ",".join("?" for _ in excluded_users)
        target.execute(
            f"DELETE FROM users WHERE id IN ({placeholders})",
            tuple(sorted(excluded_users)),
        )
    if excluded_businesses:
        placeholders = ",".join("?" for _ in excluded_businesses)
        target.execute(
            f"DELETE FROM businesses WHERE id IN ({placeholders})",
            tuple(sorted(excluded_businesses)),
        )
    target.commit()
    target.row_factory = sqlite3.Row
    return target


def _optional_rows(source: sqlite3.Connection, table: str) -> list[dict[str, object]]:
    exists = source.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    if not exists:
        return []
    try:
        return [
            dict(row) for row in source.execute(f'SELECT * FROM "{table}"').fetchall()
        ]
    except sqlite3.DatabaseError:
        return []


def _json_safe(value):
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, float):
        return value if isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value) -> float:
    try:
        parsed = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return parsed if isfinite(parsed) else 0.0


def _counters() -> dict[str, int]:
    return {"created": 0, "reused": 0, "updated": 0, "quarantined": 0, "issues": 0}


def _combine(first: StageResult, second: StageResult) -> StageResult:
    return StageResult(
        created=first.created + second.created,
        reused=first.reused + second.reused,
        updated=first.updated + second.updated,
        quarantined=first.quarantined + second.quarantined,
        issues=first.issues + second.issues,
    )
