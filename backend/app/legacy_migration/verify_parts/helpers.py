"""Demo yozuvni aniqlash va sonlarni solishtirish."""

from __future__ import annotations

from typing import Any

from app.legacy_migration.verify_parts.constants import (
    EXPLICIT_DEMO_FLAGS,
    SENSITIVE_CABINET_KEYS,
    SENSITIVE_CABINET_SUFFIXES,
    GateResult,
)


def _is_explicit_demo(
    row: dict[str, Any],
    *,
    ignored_flags: frozenset[str] = frozenset(),
) -> bool:
    return any(
        _truthy(row.get(key))
        for key in EXPLICIT_DEMO_FLAGS
        if key in row and key not in ignored_flags
    )


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


def _is_sensitive_key(key: str) -> bool:
    normalized = key.casefold()
    return normalized in SENSITIVE_CABINET_KEYS or any(
        normalized.endswith(suffix) for suffix in SENSITIVE_CABINET_SUFFIXES
    )


def _equal(code: str, actual: object, expected: object) -> GateResult:
    return GateResult(
        code=code,
        passed=actual == expected,
        actual=actual,
        expected=expected,
    )


def _zero(code: str, actual: int) -> GateResult:
    return _equal(code, actual, 0)
