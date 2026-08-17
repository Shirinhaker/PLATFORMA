"""Manba qatorlarini tozalash: matn, son, sana, telefon."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from math import isfinite


def source_row_hash(
    entity_type: str,
    row: Mapping[str, object],
) -> str:
    payload = {
        "entity_type": entity_type,
        "row": {key: row[key] for key in sorted(row)},
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _parse_work_hours(value: object) -> dict[str, object]:
    text = _text(value)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"raw": text}
    return parsed if isinstance(parsed, dict) else {"raw": text}


def _normalize_phone(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


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
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def _float_or(value: object, default: float) -> float:
    parsed = _optional_float(value)
    return default if parsed is None else parsed


def _unix_datetime(value: object) -> datetime:
    timestamp = _optional_int(value)
    if timestamp is None:
        return datetime.now(UTC)
    return datetime.fromtimestamp(timestamp, tz=UTC)
