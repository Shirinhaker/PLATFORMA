from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping


@dataclass(frozen=True)
class PayloadParity:
    ok: bool
    source_resources: int
    target_resources: int
    source_records: int
    target_records: int
    source_digest: str
    target_digest: str


def payload_digest(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_payload_parity(
    source: Mapping[str, object],
    target: Mapping[str, object],
) -> PayloadParity:
    normalized_source = _normalized_payload(source)
    normalized_target = _normalized_payload(target)
    source_digest = payload_digest(normalized_source)
    target_digest = payload_digest(normalized_target)
    source_records = sum(len(rows) for rows in normalized_source.values())
    target_records = sum(len(rows) for rows in normalized_target.values())
    return PayloadParity(
        ok=(
            len(normalized_source) == len(normalized_target)
            and source_records == target_records
            and source_digest == target_digest
        ),
        source_resources=len(normalized_source),
        target_resources=len(normalized_target),
        source_records=source_records,
        target_records=target_records,
        source_digest=source_digest,
        target_digest=target_digest,
    )


def _normalized_payload(payload: Mapping[str, object]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for resource, value in sorted(payload.items()):
        if isinstance(value, list):
            rows = [item if isinstance(item, dict) else {"value": item} for item in value]
        elif isinstance(value, dict):
            rows = [value]
        elif value is None:
            rows = []
        else:
            rows = [{"value": value}]
        if rows:
            result[str(resource)] = rows
    return result
