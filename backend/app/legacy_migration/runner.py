from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import inspect
from typing import Any

from sqlalchemy import select

from app.core.config import Settings
from app.db.session import Database
from app.legacy_migration.advertisement_stage import import_advertisements
from app.legacy_migration.catalog_stage import import_catalog
from app.legacy_migration.listing_stage import import_listings
from app.legacy_migration.media_stage import migrate_media
from app.legacy_migration.model import (
    MigrationEnvironment,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
)
from app.legacy_migration.reconcile import (
    StageResult,
    reconcile_accounts,
    reconcile_businesses,
)
from app.legacy_migration.source import (
    SnapshotInfo,
    file_sha256,
    inventory_source,
    open_immutable,
)
from app.legacy_migration.verify import (
    VerificationReport,
    verify_migration,
)
from app.media.storage import R2Storage


class ProductionGateError(RuntimeError):
    pass


class SnapshotFingerprintError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProductionApproval:
    typed_environment: str
    typed_snapshot_sha256: str
    maintenance_enabled: bool
    approved_staging_run_id: int


@dataclass(frozen=True)
class StageDefinition:
    stage: MigrationStage


STAGES: tuple[StageDefinition, ...] = tuple(
    StageDefinition(stage)
    for stage in (
        MigrationStage.INVENTORY,
        MigrationStage.ACCOUNTS,
        MigrationStage.BUSINESSES,
        MigrationStage.CATALOG,
        MigrationStage.LISTINGS,
        MigrationStage.ADVERTISEMENTS,
        MigrationStage.MEDIA,
        MigrationStage.VERIFY,
    )
)


RunLoader = Callable[
    [SnapshotInfo, str, ProductionApproval | None],
    Awaitable[MigrationRun],
]
RunSaver = Callable[[MigrationRun], Awaitable[MigrationRun] | MigrationRun]
StageHandler = Callable[
    [SnapshotInfo, MigrationRun],
    Awaitable[StageResult | VerificationReport | Mapping[str, Any]],
]
StagingValidator = Callable[
    [int, SnapshotInfo],
    Awaitable[bool] | bool,
]


class MigrationRunner:
    def __init__(
        self,
        *,
        load_or_create: RunLoader,
        save: RunSaver,
        stage_handlers: Mapping[MigrationStage, StageHandler],
        validate_staging: StagingValidator | None = None,
    ) -> None:
        self.load_or_create = load_or_create
        self.save = save
        self.stage_handlers = dict(stage_handlers)
        self.validate_staging = validate_staging

    async def run(
        self,
        snapshot: SnapshotInfo,
        environment: str,
        until_stage: str | None = None,
        *,
        approval: ProductionApproval | None = None,
    ) -> MigrationRun:
        self._validate_snapshot(snapshot)
        await self._validate_production(snapshot, environment, approval)
        run = await self.load_or_create(snapshot, environment, approval)
        completed_run = (
            run.status is MigrationStatus.COMPLETED
            and run.stage is MigrationStage.VERIFY
        )
        idempotency_mode = completed_run or bool(
            run.counters_json.get("idempotency_in_progress")
        )
        if completed_run:
            counters = dict(run.counters_json)
            counters["idempotency"] = {}
            counters["idempotency_created"] = 0
            counters["idempotency_in_progress"] = True
            run.counters_json = counters
            run.stage = MigrationStage.SNAPSHOT
            run.finished_at = None
        run.status = MigrationStatus.RUNNING

        definitions = self._remaining_stages(run)
        for definition in definitions:
            handler = self.stage_handlers.get(definition.stage)
            if handler is None:
                raise RuntimeError(
                    f"migration_stage_handler_missing:{definition.stage.value}"
                )
            try:
                result = await handler(snapshot, run)
            except Exception:
                run.status = MigrationStatus.FAILED
                run.error_count += 1
                run.finished_at = datetime.now(UTC)
                await _await_if_needed(self.save(run))
                raise

            run.stage = definition.stage
            counters = dict(run.counters_json)
            payload = _result_payload(result)
            if idempotency_mode:
                idempotency = dict(counters.get("idempotency") or {})
                idempotency[definition.stage.value] = payload
                counters["idempotency"] = idempotency
                counters["idempotency_created"] = sum(
                    int(stage_result.get("created", 0))
                    for stage, stage_result in idempotency.items()
                    if stage != MigrationStage.VERIFY.value
                )
            else:
                counters[definition.stage.value] = payload
            run.counters_json = counters
            if definition.stage is MigrationStage.VERIFY:
                verification = result
                passed = (
                    verification.passed
                    if isinstance(verification, VerificationReport)
                    else bool(payload.get("passed"))
                )
                run.status = (
                    MigrationStatus.COMPLETED
                    if passed
                    else MigrationStatus.FAILED
                )
                run.finished_at = datetime.now(UTC)
                if idempotency_mode:
                    counters.pop("idempotency_in_progress", None)
                    run.counters_json = counters
            run = await _await_if_needed(self.save(run))
            if until_stage == definition.stage.value:
                break
            if run.status is MigrationStatus.FAILED:
                break
        return run

    def _validate_snapshot(self, snapshot: SnapshotInfo) -> None:
        if file_sha256(snapshot.path) != snapshot.database_sha256:
            raise SnapshotFingerprintError(
                "snapshot_database_fingerprint_mismatch"
            )
        if file_sha256(snapshot.manifest_path) != snapshot.manifest_sha256:
            raise SnapshotFingerprintError(
                "snapshot_manifest_fingerprint_mismatch"
            )

    async def _validate_production(
        self,
        snapshot: SnapshotInfo,
        environment: str,
        approval: ProductionApproval | None,
    ) -> None:
        if environment != "production":
            return
        if approval is None:
            raise ProductionGateError(
                "production_confirmation_required"
            )
        if approval.typed_environment != "production":
            raise ProductionGateError(
                "production_environment_confirmation_mismatch"
            )
        if approval.typed_snapshot_sha256 != snapshot.database_sha256:
            raise ProductionGateError(
                "production_snapshot_confirmation_mismatch"
            )
        if not approval.maintenance_enabled:
            raise ProductionGateError("production_maintenance_required")
        if self.validate_staging is None:
            raise ProductionGateError("approved_staging_run_required")
        valid = await _await_if_needed(
            self.validate_staging(
                approval.approved_staging_run_id,
                snapshot,
            )
        )
        if not valid:
            raise ProductionGateError("approved_staging_run_invalid")

    def _remaining_stages(
        self,
        run: MigrationRun,
    ) -> tuple[StageDefinition, ...]:
        if run.stage is MigrationStage.SNAPSHOT:
            return STAGES
        for index, definition in enumerate(STAGES):
            if definition.stage is run.stage:
                return STAGES[index + 1 :]
        return STAGES


def _result_payload(
    result: StageResult | VerificationReport | Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(result, (StageResult, VerificationReport)):
        return asdict(result)
    return dict(result)


async def _await_if_needed(value):
    return await value if inspect.isawaitable(value) else value


def build_database_runner(
    database: Database,
    settings: Settings,
    storage: R2Storage,
) -> MigrationRunner:
    async def load_or_create(
        snapshot: SnapshotInfo,
        environment: str,
        approval: ProductionApproval | None,
    ) -> MigrationRun:
        target_environment = MigrationEnvironment(environment)
        async with database.session() as session:
            async with session.begin():
                existing = await session.scalar(
                    select(MigrationRun)
                    .where(
                        MigrationRun.source_database_sha256
                        == snapshot.database_sha256,
                        MigrationRun.media_manifest_sha256
                        == snapshot.manifest_sha256,
                        MigrationRun.environment == target_environment,
                    )
                    .order_by(MigrationRun.id.desc())
                    .limit(1)
                )
                if existing is not None:
                    return existing
                run = MigrationRun(
                    source_database_sha256=snapshot.database_sha256,
                    media_manifest_sha256=snapshot.manifest_sha256,
                    schema_version="0003_phase3c_content",
                    environment=target_environment,
                    stage=MigrationStage.SNAPSHOT,
                    status=MigrationStatus.RUNNING,
                    counters_json={},
                    error_count=0,
                    approved_staging_run_id=(
                        approval.approved_staging_run_id
                        if approval is not None
                        else None
                    ),
                    started_at=datetime.now(UTC),
                )
                session.add(run)
                await session.flush()
                return run

    async def save(run: MigrationRun) -> MigrationRun:
        async with database.session() as session:
            async with session.begin():
                saved = await session.merge(run)
                await session.flush()
                return saved

    async def validate_staging(
        run_id: int,
        snapshot: SnapshotInfo,
    ) -> bool:
        async with database.session() as session:
            run = await session.get(MigrationRun, run_id)
            return bool(
                run is not None
                and run.environment is MigrationEnvironment.STAGING
                and run.status is MigrationStatus.COMPLETED
                and run.stage is MigrationStage.VERIFY
                and run.schema_version == "0003_phase3c_content"
                and run.source_database_sha256 == snapshot.database_sha256
                and run.media_manifest_sha256 == snapshot.manifest_sha256
                and (run.counters_json.get("verify") or {}).get("passed")
            )

    async def inventory_handler(snapshot, run):
        async with database.session() as session:
            async with session.begin():
                source = open_immutable(snapshot.path)
                try:
                    return {"inventory": inventory_source(source)}
                finally:
                    source.close()

    async def transaction_stage(snapshot, run, function):
        async with database.session() as session:
            async with session.begin():
                source = open_immutable(snapshot.path)
                try:
                    return await function(session, source, run)
                finally:
                    source.close()

    handlers: dict[MigrationStage, StageHandler] = {
        MigrationStage.INVENTORY: inventory_handler,
        MigrationStage.ACCOUNTS: lambda snapshot, run: transaction_stage(
            snapshot,
            run,
            reconcile_accounts,
        ),
        MigrationStage.BUSINESSES: lambda snapshot, run: transaction_stage(
            snapshot,
            run,
            reconcile_businesses,
        ),
        MigrationStage.CATALOG: lambda snapshot, run: transaction_stage(
            snapshot,
            run,
            import_catalog,
        ),
        MigrationStage.LISTINGS: lambda snapshot, run: transaction_stage(
            snapshot,
            run,
            import_listings,
        ),
        MigrationStage.ADVERTISEMENTS: (
            lambda snapshot, run: transaction_stage(
                snapshot,
                run,
                import_advertisements,
            )
        ),
        MigrationStage.MEDIA: (
            lambda snapshot, run: _media_transaction(
                database,
                snapshot,
                run,
                storage,
                settings,
            )
        ),
        MigrationStage.VERIFY: lambda snapshot, run: transaction_stage(
            snapshot,
            run,
            verify_migration,
        ),
    }
    return MigrationRunner(
        load_or_create=load_or_create,
        save=save,
        stage_handlers=handlers,
        validate_staging=validate_staging,
    )


async def _media_transaction(
    database: Database,
    snapshot: SnapshotInfo,
    run: MigrationRun,
    storage: R2Storage,
    settings: Settings,
) -> StageResult:
    async with database.session() as session:
        async with session.begin():
            source = open_immutable(snapshot.path)
            try:
                return await migrate_media(
                    session,
                    source,
                    storage,
                    settings,
                    run,
                )
            finally:
                source.close()
