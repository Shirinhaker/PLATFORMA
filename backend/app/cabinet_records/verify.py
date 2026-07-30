from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping


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
    normalized_source = _canonical_payload(source)
    normalized_target = _canonical_payload(target)
    source_digest = payload_digest(normalized_source)
    target_digest = payload_digest(normalized_target)
    source_records = sum(_record_count(value) for value in normalized_source.values())
    target_records = sum(_record_count(value) for value in normalized_target.values())
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


def aggregate_profile_digest(entries: list[tuple[str, str]]) -> str:
    """Stable digest for sorted ``account_type:account_id`` profile digests."""
    ordered = sorted(entries, key=lambda entry: entry[0])
    return payload_digest([{"profile": key, "digest": digest} for key, digest in ordered])


def _canonical_payload(payload: Mapping[str, object]) -> dict[str, object]:
    return {str(resource): value for resource, value in sorted(payload.items())}


def _record_count(value: object) -> int:
    if isinstance(value, list):
        return len(value)
    if value is None:
        return 0
    return 1
