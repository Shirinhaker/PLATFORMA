from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cabinet_records.batch_runner import load_profile, profile_payload, profile_refs
from app.cabinet_records.model import CabinetResource
from app.cabinet_records.repository import CabinetRecordRepository
from app.cabinet_records.security import assert_payload_safe
from app.cabinet_records.verify import (
    aggregate_profile_digest,
    payload_digest,
    verify_payload_parity,
)


@dataclass(frozen=True)
class ExistingNormalizationVerification:
    ok: bool
    profiles_total: int
    profiles_verified: int
    resources_source: int
    resources_target: int
    records_source: int
    records_target: int
    source_digest: str
    target_digest: str
    marker_mismatches: int


async def verify_existing_normalization(
    session: AsyncSession,
    *,
    repository: CabinetRecordRepository | None = None,
) -> ExistingNormalizationVerification:
    repo = repository or CabinetRecordRepository()
    refs = await profile_refs(session)
    source_entries: list[tuple[str, str]] = []
    target_entries: list[tuple[str, str]] = []
    profiles_verified = 0
    resources_source = 0
    resources_target = 0
    records_source = 0
    records_target = 0
    marker_mismatches = 0

    for ref in refs:
        profile = await load_profile(session, ref)
        source_payload = profile_payload(profile.cabinet_payload)
        assert_payload_safe(source_payload)
        target_payload = await repo.read_payload(
            session,
            account_id=ref.account_id,
            account_type=ref.account_type,
        )
        parity = verify_payload_parity(source_payload, target_payload)
        profile_key = f"{ref.account_type}:{ref.account_id}"
        source_entries.append((profile_key, parity.source_digest))
        target_entries.append((profile_key, parity.target_digest))
        resources_source += parity.source_resources
        resources_target += parity.target_resources
        records_source += parity.source_records
        records_target += parity.target_records
        if parity.ok:
            profiles_verified += 1

        markers = list(
            (
                await session.scalars(
                    select(CabinetResource).where(
                        CabinetResource.account_id == ref.account_id,
                        CabinetResource.account_type == ref.account_type,
                    )
                )
            ).all()
        )
        for marker in markers:
            value = target_payload.get(marker.resource)
            expected_count = len(value) if isinstance(value, list) else (0 if value is None else 1)
            if marker.record_count != expected_count or marker.digest != payload_digest(value):
                marker_mismatches += 1

    source_digest = aggregate_profile_digest(source_entries)
    target_digest = aggregate_profile_digest(target_entries)
    return ExistingNormalizationVerification(
        ok=(
            profiles_verified == len(refs)
            and resources_source == resources_target
            and records_source == records_target
            and source_digest == target_digest
            and marker_mismatches == 0
        ),
        profiles_total=len(refs),
        profiles_verified=profiles_verified,
        resources_source=resources_source,
        resources_target=resources_target,
        records_source=records_source,
        records_target=records_target,
        source_digest=source_digest,
        target_digest=target_digest,
        marker_mismatches=marker_mismatches,
    )
