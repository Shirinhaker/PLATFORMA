from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cabinet_records.contract import NORMALIZATION_SCHEMA_VERSION
from app.cabinet_records.model import CabinetNormalizationRun
from app.cabinet_records.repository import CabinetRecordRepository
from app.cabinet_records.verify import PayloadParity, payload_digest, verify_payload_parity
from app.profiles.model import BusinessProfile, UserProfile


class NormalizationParityError(RuntimeError):
    pass


@dataclass(frozen=True)
class NormalizationSummary:
    run_id: int
    profiles_total: int
    profiles_verified: int
    resources_source: int
    resources_target: int
    records_source: int
    records_target: int
    source_digest: str
    target_digest: str


async def backfill_all_profiles(
    session: AsyncSession,
    *,
    repository: CabinetRecordRepository | None = None,
) -> NormalizationSummary:
    repo = repository or CabinetRecordRepository()
    run = CabinetNormalizationRun(
        schema_version=NORMALIZATION_SCHEMA_VERSION,
        status="running",
    )
    session.add(run)
    await session.flush()

    source_bundle: dict[str, object] = {}
    target_bundle: dict[str, object] = {}
    profiles_total = 0
    profiles_verified = 0
    resources_source = 0
    resources_target = 0
    records_source = 0
    records_target = 0

    try:
        user_profiles = list(
            (await session.scalars(select(UserProfile).order_by(UserProfile.account_id))).all()
        )
        business_profiles = list(
            (
                await session.scalars(
                    select(BusinessProfile).order_by(BusinessProfile.account_id)
                )
            ).all()
        )

        for account_type, profiles in (
            ("user", user_profiles),
            ("business", business_profiles),
        ):
            for profile in profiles:
                profiles_total += 1
                source_payload = _payload(profile.cabinet_payload)
                await repo.replace_payload(
                    session,
                    account_id=profile.account_id,
                    account_type=account_type,
                    payload=source_payload,
                )
                target_payload = await repo.read_payload(
                    session,
                    account_id=profile.account_id,
                    account_type=account_type,
                )
                parity = verify_payload_parity(source_payload, target_payload)
                _accumulate_or_raise(
                    parity,
                    account_type=account_type,
                    account_id=profile.account_id,
                )
                profiles_verified += 1
                resources_source += parity.source_resources
                resources_target += parity.target_resources
                records_source += parity.source_records
                records_target += parity.target_records
                key = f"{account_type}:{profile.account_id}"
                source_bundle[key] = source_payload
                target_bundle[key] = target_payload

        source_digest = payload_digest(source_bundle)
        target_digest = payload_digest(target_bundle)
        if source_digest != target_digest:
            raise NormalizationParityError("cabinet_normalization_global_digest_mismatch")

        run.status = "verified"
        run.completed_at = datetime.now(UTC)
        run.profiles_total = profiles_total
        run.profiles_verified = profiles_verified
        run.resources_source = resources_source
        run.resources_target = resources_target
        run.records_source = records_source
        run.records_target = records_target
        run.source_digest = source_digest
        run.target_digest = target_digest
        run.error_code = ""
        await session.flush()
        return NormalizationSummary(
            run_id=run.id,
            profiles_total=profiles_total,
            profiles_verified=profiles_verified,
            resources_source=resources_source,
            resources_target=resources_target,
            records_source=records_source,
            records_target=records_target,
            source_digest=source_digest,
            target_digest=target_digest,
        )
    except Exception as exc:
        run.status = "failed"
        run.completed_at = datetime.now(UTC)
        run.profiles_total = profiles_total
        run.profiles_verified = profiles_verified
        run.resources_source = resources_source
        run.resources_target = resources_target
        run.records_source = records_source
        run.records_target = records_target
        run.error_code = str(exc)[:120]
        await session.flush()
        raise


def _payload(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _accumulate_or_raise(
    parity: PayloadParity,
    *,
    account_type: str,
    account_id: int,
) -> None:
    if parity.ok:
        return
    raise NormalizationParityError(
        "cabinet_normalization_profile_mismatch:"
        f"{account_type}:{account_id}:"
        f"resources={parity.source_resources}/{parity.target_resources}:"
        f"records={parity.source_records}/{parity.target_records}:"
        f"digest={parity.source_digest}/{parity.target_digest}"
    )
