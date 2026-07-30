from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cabinet_records.contract import NORMALIZATION_SCHEMA_VERSION
from app.cabinet_records.model import CabinetNormalizationRun
from app.cabinet_records.repository import CabinetRecordRepository
from app.cabinet_records.security import assert_payload_safe
from app.cabinet_records.verify import (
    aggregate_profile_digest,
    payload_digest,
    verify_payload_parity,
)
from app.profiles.model import BusinessProfile, UserProfile


SessionFactory = Callable[[], AsyncIterator[AsyncSession]]


@dataclass(frozen=True, order=True)
class ProfileRef:
    account_type: str
    account_id: int


@dataclass(frozen=True)
class BatchNormalizationSummary:
    run_id: int
    status: str
    profiles_total: int
    profiles_verified: int
    resources_source: int
    resources_target: int
    records_source: int
    records_target: int
    source_digest: str
    target_digest: str
    batches_committed: int


class BatchNormalizationError(RuntimeError):
    pass


async def execute_backfill_batches(
    session_factory: SessionFactory,
    *,
    batch_size: int = 100,
    repository: CabinetRecordRepository | None = None,
) -> BatchNormalizationSummary:
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size 1 dan 1000 gacha bo‘lishi kerak")
    repo = repository or CabinetRecordRepository()

    async with session_factory() as session:
        refs = await profile_refs(session)
        run = CabinetNormalizationRun(
            schema_version=NORMALIZATION_SCHEMA_VERSION,
            status="running",
            profiles_total=len(refs),
        )
        session.add(run)
        await session.flush()
        run_id = run.id
        await session.commit()

    profiles_verified = 0
    resources_source = 0
    resources_target = 0
    records_source = 0
    records_target = 0
    source_entries: list[tuple[str, str]] = []
    target_entries: list[tuple[str, str]] = []
    batches_committed = 0

    try:
        for start in range(0, len(refs), batch_size):
            batch = refs[start:start + batch_size]
            async with session_factory() as session:
                run = await session.get(CabinetNormalizationRun, run_id)
                if run is None:
                    raise BatchNormalizationError("cabinet_normalization_run_missing")

                for ref in batch:
                    profile = await load_profile(session, ref)
                    source_payload = profile_payload(profile.cabinet_payload)
                    assert_payload_safe(source_payload)
                    await repo.replace_payload(
                        session,
                        account_id=ref.account_id,
                        account_type=ref.account_type,
                        payload=source_payload,
                    )
                    target_payload = await repo.read_payload(
                        session,
                        account_id=ref.account_id,
                        account_type=ref.account_type,
                    )
                    parity = verify_payload_parity(source_payload, target_payload)
                    if not parity.ok:
                        raise BatchNormalizationError(
                            "cabinet_normalization_profile_mismatch:"
                            f"{ref.account_type}:{ref.account_id}:"
                            f"resources={parity.source_resources}/{parity.target_resources}:"
                            f"records={parity.source_records}/{parity.target_records}:"
                            f"digest={parity.source_digest}/{parity.target_digest}"
                        )

                    profile_key = f"{ref.account_type}:{ref.account_id}"
                    source_entries.append((profile_key, parity.source_digest))
                    target_entries.append((profile_key, parity.target_digest))
                    profiles_verified += 1
                    resources_source += parity.source_resources
                    resources_target += parity.target_resources
                    records_source += parity.source_records
                    records_target += parity.target_records

                batches_committed += 1
                run.profiles_verified = profiles_verified
                run.resources_source = resources_source
                run.resources_target = resources_target
                run.records_source = records_source
                run.records_target = records_target
                run.source_digest = aggregate_profile_digest(source_entries)
                run.target_digest = aggregate_profile_digest(target_entries)
                await session.commit()

        source_digest = aggregate_profile_digest(source_entries)
        target_digest = aggregate_profile_digest(target_entries)
        if source_digest != target_digest or profiles_verified != len(refs):
            raise BatchNormalizationError("cabinet_normalization_global_mismatch")

        async with session_factory() as session:
            run = await session.get(CabinetNormalizationRun, run_id)
            if run is None:
                raise BatchNormalizationError("cabinet_normalization_run_missing")
            run.status = "verified"
            run.completed_at = datetime.now(UTC)
            run.profiles_total = len(refs)
            run.profiles_verified = profiles_verified
            run.resources_source = resources_source
            run.resources_target = resources_target
            run.records_source = records_source
            run.records_target = records_target
            run.source_digest = source_digest
            run.target_digest = target_digest
            run.error_code = ""
            await session.commit()

        return BatchNormalizationSummary(
            run_id=run_id,
            status="verified",
            profiles_total=len(refs),
            profiles_verified=profiles_verified,
            resources_source=resources_source,
            resources_target=resources_target,
            records_source=records_source,
            records_target=records_target,
            source_digest=source_digest,
            target_digest=target_digest,
            batches_committed=batches_committed,
        )
    except Exception as exc:
        await mark_run_failed(
            session_factory,
            run_id=run_id,
            profiles_total=len(refs),
            profiles_verified=profiles_verified,
            resources_source=resources_source,
            resources_target=resources_target,
            records_source=records_source,
            records_target=records_target,
            source_entries=source_entries,
            target_entries=target_entries,
            error_code=str(exc)[:120],
        )
        raise


async def profile_refs(session: AsyncSession) -> list[ProfileRef]:
    user_ids = list(
        (await session.scalars(select(UserProfile.account_id).order_by(UserProfile.account_id))).all()
    )
    business_ids = list(
        (
            await session.scalars(
                select(BusinessProfile.account_id).order_by(BusinessProfile.account_id)
            )
        ).all()
    )
    return [
        *[ProfileRef("user", int(account_id)) for account_id in user_ids],
        *[ProfileRef("business", int(account_id)) for account_id in business_ids],
    ]


async def load_profile(session: AsyncSession, ref: ProfileRef):
    model = UserProfile if ref.account_type == "user" else BusinessProfile
    profile = await session.get(model, ref.account_id)
    if profile is None:
        raise BatchNormalizationError(
            f"cabinet_normalization_profile_missing:{ref.account_type}:{ref.account_id}"
        )
    return profile


def profile_payload(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


async def mark_run_failed(
    session_factory: SessionFactory,
    *,
    run_id: int,
    profiles_total: int,
    profiles_verified: int,
    resources_source: int,
    resources_target: int,
    records_source: int,
    records_target: int,
    source_entries: list[tuple[str, str]],
    target_entries: list[tuple[str, str]],
    error_code: str,
) -> None:
    async with session_factory() as session:
        run = await session.get(CabinetNormalizationRun, run_id)
        if run is None:
            return
        run.status = "failed"
        run.completed_at = datetime.now(UTC)
        run.profiles_total = profiles_total
        run.profiles_verified = profiles_verified
        run.resources_source = resources_source
        run.resources_target = resources_target
        run.records_source = records_source
        run.records_target = records_target
        run.source_digest = aggregate_profile_digest(source_entries)
        run.target_digest = aggregate_profile_digest(target_entries)
        run.error_code = error_code
        await session.commit()
