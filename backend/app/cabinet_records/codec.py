from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Iterable


MIN_BIGINT = -(2**63)
MAX_BIGINT = 2**63 - 1


@dataclass(frozen=True)
class FlatRecord:
    account_id: int
    account_type: str
    resource: str
    source_key: str
    ordinal: int
    value_kind: str = "object"

    @property
    def payload_json(self) -> None:
        return None


@dataclass(frozen=True)
class FlatField:
    record_source_key: str
    path: str
    value_type: str
    value_text: str | None = None
    value_integer: int | None = None
    value_float: float | None = None
    value_boolean: bool | None = None

    @property
    def value_json(self) -> None:
        return None


def flatten_records(
    *,
    account_id: int,
    account_type: str,
    resource: str,
    rows: Iterable[object],
) -> tuple[list[FlatRecord], list[FlatField]]:
    records: list[FlatRecord] = []
    fields: list[FlatField] = []
    used_keys: set[str] = set()

    for ordinal, raw_row in enumerate(rows):
        row = raw_row if isinstance(raw_row, dict) else {"value": raw_row}
        source_key = _source_key(row, ordinal, used_keys)
        records.append(
            FlatRecord(
                account_id=account_id,
                account_type=account_type,
                resource=resource,
                source_key=source_key,
                ordinal=ordinal,
                value_kind=_record_value_kind(raw_row),
            )
        )
        for key, value in row.items():
            _flatten_value(
                fields,
                record_source_key=source_key,
                path=(str(key),),
                value=value,
            )

    return records, fields


def inflate_records(
    records: Iterable[object],
    fields: Iterable[object],
) -> list[Any]:
    ordered_records = sorted(records, key=lambda record: int(getattr(record, "ordinal")))
    fields_by_key: dict[str, list[object]] = {}
    for field in fields:
        key = str(getattr(field, "record_source_key"))
        fields_by_key.setdefault(key, []).append(field)

    result: list[Any] = []
    for record in ordered_records:
        source_key = str(getattr(record, "source_key"))
        root: dict[str, Any] = {}
        record_fields = sorted(
            fields_by_key.get(source_key, []),
            key=lambda field: (
                len(_decode_path(str(getattr(field, "path")))),
                str(getattr(field, "path")),
            ),
        )
        for field in record_fields:
            segments = _decode_path(str(getattr(field, "path")))
            _assign(
                root,
                segments,
                _field_value(field),
            )
        value_kind = str(getattr(record, "value_kind", "object"))
        if value_kind == "object":
            result.append(root)
        elif value_kind == "null":
            result.append(None)
        else:
            result.append(root.get("value"))
    return result


def normalize_payload_rows(value: object) -> list[object]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return [value]
    if value is None:
        return []
    return [value]


def _record_value_kind(value: object) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "list"
    if value is None:
        return "null"
    return "scalar"


def _source_key(row: dict[str, Any], ordinal: int, used_keys: set[str]) -> str:
    candidate = str(row.get("id") if row.get("id") is not None else f"ordinal:{ordinal}")
    suffix = 1
    key = _bounded_key(candidate)
    while key in used_keys:
        suffix += 1
        key = _bounded_key(f"{candidate}#{suffix}")
    used_keys.add(key)
    return key


def _bounded_key(value: str) -> str:
    if len(value) <= 160:
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:40]
    return f"{value[:119]}:{digest}"


def _flatten_value(
    fields: list[FlatField],
    *,
    record_source_key: str,
    path: tuple[str, ...],
    value: object,
) -> None:
    encoded = _encode_path(path)
    if isinstance(value, dict):
        fields.append(
            FlatField(
                record_source_key=record_source_key,
                path=encoded,
                value_type="object",
            )
        )
        for key, child in value.items():
            _flatten_value(
                fields,
                record_source_key=record_source_key,
                path=(*path, str(key)),
                value=child,
            )
        return

    if isinstance(value, list):
        fields.append(
            FlatField(
                record_source_key=record_source_key,
                path=encoded,
                value_type="list",
            )
        )
        for index, child in enumerate(value):
            _flatten_value(
                fields,
                record_source_key=record_source_key,
                path=(*path, str(index)),
                value=child,
            )
        return

    if value is None:
        fields.append(
            FlatField(
                record_source_key=record_source_key,
                path=encoded,
                value_type="null",
            )
        )
    elif isinstance(value, bool):
        fields.append(
            FlatField(
                record_source_key=record_source_key,
                path=encoded,
                value_type="boolean",
                value_boolean=value,
            )
        )
    elif isinstance(value, int):
        if MIN_BIGINT <= value <= MAX_BIGINT:
            fields.append(
                FlatField(
                    record_source_key=record_source_key,
                    path=encoded,
                    value_type="integer",
                    value_integer=value,
                )
            )
        else:
            fields.append(
                FlatField(
                    record_source_key=record_source_key,
                    path=encoded,
                    value_type="big_integer",
                    value_text=str(value),
                )
            )
    elif isinstance(value, float):
        fields.append(
            FlatField(
                record_source_key=record_source_key,
                path=encoded,
                value_type="float",
                value_float=value,
            )
        )
    else:
        fields.append(
            FlatField(
                record_source_key=record_source_key,
                path=encoded,
                value_type="string",
                value_text=str(value),
            )
        )


def _field_value(field: object) -> object:
    value_type = str(getattr(field, "value_type"))
    if value_type == "object":
        return {}
    if value_type == "list":
        return []
    if value_type == "null":
        return None
    if value_type == "boolean":
        return bool(getattr(field, "value_boolean"))
    if value_type == "integer":
        return int(getattr(field, "value_integer"))
    if value_type == "big_integer":
        return int(str(getattr(field, "value_text")))
    if value_type == "float":
        return float(getattr(field, "value_float"))
    return str(getattr(field, "value_text"))


def _assign(
    root: dict[str, Any],
    segments: tuple[str, ...],
    value: object,
) -> None:
    if not segments:
        return
    current: Any = root
    for index, segment in enumerate(segments[:-1]):
        next_segment = segments[index + 1]
        next_is_index = next_segment.isdigit()
        if isinstance(current, list):
            position = int(segment)
            _ensure_list_size(current, position)
            if current[position] is None:
                current[position] = [] if next_is_index else {}
            current = current[position]
        else:
            if segment not in current or current[segment] is None:
                current[segment] = [] if next_is_index else {}
            current = current[segment]

    leaf = segments[-1]
    if isinstance(current, list):
        position = int(leaf)
        _ensure_list_size(current, position)
        current[position] = value
    else:
        current[leaf] = value


def _ensure_list_size(value: list[Any], position: int) -> None:
    while len(value) <= position:
        value.append(None)


def _encode_path(parts: tuple[str, ...]) -> str:
    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)


def _decode_path(path: str) -> tuple[str, ...]:
    if not path:
        return ()
    return tuple(part.replace("~1", "/").replace("~0", "~") for part in path.lstrip("/").split("/"))
