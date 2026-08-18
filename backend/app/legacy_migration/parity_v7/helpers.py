"""Qator tozalash va maxfiy maydonlarni yashirish."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.legacy_migration.parity_v7.constants import (
    _DROP,
    EXPLICIT_DEMO_FLAGS,
    SENSITIVE_KEYS,
    SENSITIVE_SUFFIXES,
)


async def _target_tables_exist(
    session: AsyncSession,
    *table_names: str,
) -> bool:
    connection = await session.connection()

    def inspect_tables(sync_connection) -> bool:
        inspector = sqlalchemy_inspect(sync_connection)
        return all(inspector.has_table(name) for name in table_names)

    return bool(await connection.run_sync(inspect_tables))


def _rows(source: sqlite3.Connection, table: str) -> list[dict[str, object]]:
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


def _group_rows(
    rows: list[dict[str, object]],
    key: str,
) -> dict[int, list[dict[str, object]]]:
    grouped: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[_integer(row.get(key))].append(row)
    return grouped


def _real_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [row for row in rows if not _is_explicit_demo(row)]


def _is_explicit_demo(row: dict[str, object]) -> bool:
    return any(_truthy(row.get(key)) for key in EXPLICIT_DEMO_FLAGS if key in row)


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "demo",
        "test",
    }


def _clean_payload(value: object) -> dict[str, Any]:
    sanitized = _safe_value(value)
    return sanitized if isinstance(sanitized, dict) else {}


def _safe_rows(rows: Iterable[object]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or _is_explicit_demo(row):
            continue
        sanitized = _safe_value(row)
        if isinstance(sanitized, dict):
            result.append(sanitized)
    return result


def _safe_subscription_rows(
    rows: Iterable[object],
) -> list[dict[str, Any]]:
    """Sanitize entitlements without treating activation method as identity."""
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        sanitized = _safe_value(row, preserve_demo_marker=True)
        if isinstance(sanitized, dict):
            result.append(sanitized)
    return result


def _safe_row(row: dict[str, object]) -> dict[str, Any]:
    sanitized = _safe_value(row)
    return sanitized if isinstance(sanitized, dict) else {}


def _safe_value(
    value: object,
    *,
    preserve_demo_marker: bool = False,
) -> Any:
    if isinstance(value, dict):
        if not preserve_demo_marker and _is_explicit_demo(value):
            return _DROP
        result: dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            if _is_sensitive_key(text_key):
                continue
            sanitized = _safe_value(item)
            if sanitized is not _DROP:
                result[text_key] = sanitized
        return result
    if isinstance(value, (list, tuple)):
        result: list[Any] = []
        for item in value:
            sanitized = _safe_value(item)
            if sanitized is not _DROP:
                result.append(sanitized)
        return result
    if isinstance(value, bytes):
        return {
            "binary_omitted": True,
            "size_bytes": len(value),
        }
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.casefold()
    return (
        normalized in SENSITIVE_KEYS
        or normalized.endswith("pass_hash")
        or normalized.endswith("password_hash")
        or normalized.endswith("token_hash")
        or normalized.endswith("code_hash")
        or any(normalized.endswith(suffix) for suffix in SENSITIVE_SUFFIXES)
    )


def _integer(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
