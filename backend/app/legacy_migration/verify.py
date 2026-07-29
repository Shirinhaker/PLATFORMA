from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.advertisements.model import Advertisement
from app.catalog.model import CatalogItem
from app.legacy_migration.model import (
    LegacyIdMap,
    MediaMigration,
    MediaMigrationState,
    MigrationIssue,
    MigrationRun,
)
from app.legacy_migration.source import inventory_source
from app.listings.model import Listing
from app.profiles.model import BusinessProfile, UserProfile


EXPLICIT_DEMO_FLAGS = (
    "is_demo",
    "demo",
    "is_test",
    "test_mode",
    "demo_mode",
)
SENSITIVE_CABINET_KEYS = {
    "pass_hash",
    "password_hash",
    "biz_pass_hash",
    "token_hash",
    "start_token",
    "start_token_hash",
    "code_hash",
    "secret",
    "private_key",
    "content",
}


@dataclass(frozen=True)
class GateResult:
    code: str
    passed: bool
    actual: object
    expected: object


@dataclass(frozen=True)
class VerificationReport:
    passed: bool
    gates: list[GateResult]


@dataclass(frozen=True)
class VerificationInput:
    source_rows: int
    mapped_rows: int
    source_catalog_kinds: dict[str, int]
    target_catalog_kinds: dict[str, int]
    source_listings: int
    target_listings: int
    source_advertisements: int
    target_advertisements: int
    broken_foreign_keys: int
    identity_conflicts: int
    source_media_references: int
    media_copied: int
    media_missing: int
    media_invalid: int
    media_failed: int
    copied_media_unverified: int
    idempotency_created: int
    forbidden_public_fields: tuple[str, ...]
    cabinet_demo_rows: int = 0
    cabinet_sensitive_fields: int = 0


def evaluate_gates(values: VerificationInput) -> VerificationReport:
    terminal_media = (
        values.media_copied
        + values.media_missing
        + values.media_invalid
    )
    gates = [
        _equal(
            "mapping_coverage",
            values.mapped_rows,
            values.source_rows,
        ),
        _equal(
            "catalog_kind_count",
            values.target_catalog_kinds,
            values.source_catalog_kinds,
        ),
        _equal(
            "listing_count",
            values.target_listings,
            values.source_listings,
        ),
        _equal(
            "advertisement_count",
            values.target_advertisements,
            values.source_advertisements,
        ),
        _zero("broken_foreign_keys", values.broken_foreign_keys),
        _zero("identity_conflicts", values.identity_conflicts),
        _zero("cabinet_demo_rows", values.cabinet_demo_rows),
        _zero(
            "cabinet_sensitive_fields",
            values.cabinet_sensitive_fields,
        ),
        _zero("media_failed", values.media_failed),
        _equal(
            "media_terminal_count",
            terminal_media,
            values.source_media_references,
        ),
        _zero(
            "copied_media_verification",
            values.copied_media_unverified,
        ),
        _zero("idempotency", values.idempotency_created),
        GateResult(
            code="public_schema_leak",
            passed=not values.forbidden_public_fields,
            actual=list(values.forbidden_public_fields),
            expected=[],
        ),
    ]
    return VerificationReport(
        passed=all(gate.passed for gate in gates),
        gates=gates,
    )


async def verify_migration(
    session: AsyncSession,
    source,
    run: MigrationRun,
    *,
    forbidden_public_fields: tuple[str, ...] = (),
) -> VerificationReport:
    inventory = inventory_source(source)
    entity_types = (
        "user_account",
        "business_account",
        "catalog_group",
        "catalog_item",
        "listing",
        "listing_media",
        "advertisement",
    )
    source_rows = sum(
        inventory[table]["total"]
        for table in (
            "users",
            "businesses",
            "item_groups",
            "items",
            "listings",
            "listing_media",
            "advertisements",
        )
    )
    mapped_rows = int(
        await session.scalar(
            select(func.count(LegacyIdMap.id)).where(
                LegacyIdMap.entity_type.in_(entity_types),
                LegacyIdMap.last_run_id == run.id,
            )
        )
        or 0
    )
    target_catalog = {
        str(kind): int(count)
        for kind, count in (
            await session.execute(
                select(CatalogItem.kind, func.count(CatalogItem.id))
                .where(CatalogItem.migration_run_id == run.id)
                .group_by(CatalogItem.kind)
            )
        ).all()
    }
    source_catalog = {
        kind: int(inventory["items"].get(kind, 0))
        for kind in ("product", "service")
    }
    target_listings = await _count_for_run(session, Listing, run.id)
    target_ads = await _count_for_run(session, Advertisement, run.id)
    identity_conflicts = int(
        await session.scalar(
            select(func.count(MigrationIssue.id)).where(
                MigrationIssue.migration_run_id == run.id,
                MigrationIssue.resolved.is_(False),
                MigrationIssue.issue_code.like("identity.%"),
            )
        )
        or 0
    )
    media_counts = {
        state: int(count)
        for state, count in (
            await session.execute(
                select(
                    MediaMigration.state,
                    func.count(MediaMigration.id),
                )
                .where(MediaMigration.migration_run_id == run.id)
                .group_by(MediaMigration.state)
            )
        ).all()
    }
    copied_unverified = int(
        await session.scalar(
            select(func.count(MediaMigration.id)).where(
                MediaMigration.migration_run_id == run.id,
                MediaMigration.state == MediaMigrationState.COPIED,
                (
                    (MediaMigration.destination_object_key == "")
                    | (MediaMigration.sha256 == "")
                    | (MediaMigration.content_type == "")
                    | (MediaMigration.size_bytes <= 0)
                ),
            )
        )
        or 0
    )
    cabinet_demo_rows, cabinet_sensitive_fields = (
        await _cabinet_payload_violations(session, run.id)
    )
    values = VerificationInput(
        source_rows=source_rows,
        mapped_rows=mapped_rows,
        source_catalog_kinds=source_catalog,
        target_catalog_kinds={
            kind: target_catalog.get(kind, 0)
            for kind in ("product", "service")
        },
        source_listings=inventory["listings"]["total"],
        target_listings=target_listings,
        source_advertisements=inventory["advertisements"]["total"],
        target_advertisements=target_ads,
        broken_foreign_keys=await _broken_mappings(
            session,
            entity_types,
            run.id,
        ),
        identity_conflicts=identity_conflicts,
        source_media_references=_source_media_references(source),
        media_copied=media_counts.get(MediaMigrationState.COPIED, 0),
        media_missing=media_counts.get(MediaMigrationState.MISSING, 0),
        media_invalid=media_counts.get(MediaMigrationState.INVALID, 0),
        media_failed=media_counts.get(MediaMigrationState.FAILED, 0),
        copied_media_unverified=copied_unverified,
        idempotency_created=int(
            run.counters_json.get("idempotency_created", 0)
        ),
        forbidden_public_fields=forbidden_public_fields,
        cabinet_demo_rows=cabinet_demo_rows,
        cabinet_sensitive_fields=cabinet_sensitive_fields,
    )
    return evaluate_gates(values)


async def _cabinet_payload_violations(
    session: AsyncSession,
    run_id: int,
) -> tuple[int, int]:
    mappings = (
        await session.scalars(
            select(LegacyIdMap).where(
                LegacyIdMap.entity_type.in_(
                    ("user_account", "business_account")
                ),
                LegacyIdMap.last_run_id == run_id,
                LegacyIdMap.target_id.is_not(None),
            )
        )
    ).all()
    user_ids = {
        int(mapping.target_id)
        for mapping in mappings
        if mapping.entity_type == "user_account"
        and mapping.target_id is not None
    }
    business_ids = {
        int(mapping.target_id)
        for mapping in mappings
        if mapping.entity_type == "business_account"
        and mapping.target_id is not None
    }

    payloads: list[object] = []
    if user_ids:
        payloads.extend(
            profile.cabinet_payload
            for profile in (
                await session.scalars(
                    select(UserProfile).where(
                        UserProfile.account_id.in_(user_ids)
                    )
                )
            ).all()
        )
    if business_ids:
        payloads.extend(
            profile.cabinet_payload
            for profile in (
                await session.scalars(
                    select(BusinessProfile).where(
                        BusinessProfile.account_id.in_(business_ids)
                    )
                )
            ).all()
        )

    demo_rows = 0
    sensitive_fields = 0
    for payload in payloads:
        found_demo, found_sensitive = _inspect_cabinet_value(payload)
        demo_rows += found_demo
        sensitive_fields += found_sensitive
    return demo_rows, sensitive_fields


def _inspect_cabinet_value(value: object) -> tuple[int, int]:
    if isinstance(value, dict):
        demo_rows = int(_is_explicit_demo(value))
        sensitive_fields = 0
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                sensitive_fields += 1
                continue
            child_demo, child_sensitive = _inspect_cabinet_value(item)
            demo_rows += child_demo
            sensitive_fields += child_sensitive
        return demo_rows, sensitive_fields
    if isinstance(value, list):
        demo_rows = 0
        sensitive_fields = 0
        for item in value:
            child_demo, child_sensitive = _inspect_cabinet_value(item)
            demo_rows += child_demo
            sensitive_fields += child_sensitive
        return demo_rows, sensitive_fields
    return 0, 0


def _is_explicit_demo(row: dict[str, Any]) -> bool:
    return any(
        _truthy(row.get(key))
        for key in EXPLICIT_DEMO_FLAGS
        if key in row
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
    return (
        normalized in SENSITIVE_CABINET_KEYS
        or normalized.endswith("_password")
        or normalized.endswith("_secret")
    )


async def _count_for_run(session, model, run_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count(model.id)).where(
                model.migration_run_id == run_id
            )
        )
        or 0
    )


async def _broken_mappings(
    session: AsyncSession,
    entity_types: tuple[str, ...],
    run_id: int,
) -> int:
    mappings = (
        await session.scalars(
            select(LegacyIdMap).where(
                LegacyIdMap.entity_type.in_(entity_types),
                LegacyIdMap.last_run_id == run_id,
                LegacyIdMap.target_id.is_not(None),
            )
        )
    ).all()
    models = {
        "catalog_item": CatalogItem,
        "listing": Listing,
        "advertisement": Advertisement,
    }
    broken = 0
    for mapping in mappings:
        model = models.get(mapping.entity_type)
        if model is None:
            continue
        if await session.get(model, mapping.target_id) is None:
            broken += 1
    return broken


def _source_media_references(source) -> int:
    total = 0
    queries = (
        "SELECT COUNT(*) FROM items "
        "WHERE TRIM(COALESCE(photo_file, '')) != ''",
        "SELECT COUNT(*) FROM listing_media "
        "WHERE TRIM(COALESCE(tg_file_id, '')) != ''",
        "SELECT COUNT(*) FROM advertisements "
        "WHERE TRIM(COALESCE(image_file, '')) != ''",
        "SELECT COUNT(*) FROM advertisements "
        "WHERE TRIM(COALESCE(mobile_image_file, '')) != ''",
    )
    for query in queries:
        try:
            total += int(source.execute(query).fetchone()[0])
        except Exception:
            continue
    return total


def _equal(code: str, actual: object, expected: object) -> GateResult:
    return GateResult(
        code=code,
        passed=actual == expected,
        actual=actual,
        expected=expected,
    )


def _zero(code: str, actual: int) -> GateResult:
    return _equal(code, actual, 0)
