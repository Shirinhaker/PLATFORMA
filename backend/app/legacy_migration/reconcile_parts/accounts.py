"""Akkauntlarni solishtirish va yaratish."""

from __future__ import annotations

import sqlite3
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.legacy_migration.model import (
    MigrationRun,
)
from app.legacy_migration.reconcile_parts.constants import (
    StageResult,
)
from app.legacy_migration.reconcile_parts.helpers import (
    _optional_int,
    _unix_datetime,
    source_row_hash,
)
from app.legacy_migration.reconcile_parts.lookups import (
    _account_by_login,
    _account_by_telegram,
    _ensure_user_profile,
    _identity_conflicts,
)
from app.legacy_migration.reconcile_parts.mapping import (
    _ensure_issue,
    _find_mapping,
    _upsert_mapping,
)
from app.legacy_migration.reconcile_parts.records import (
    _account_record,
    _apply_account_record,
    _legacy_business_rehome_record,
)
from app.legacy_migration.reconcile_parts.source import (
    _source_rows,
)


async def reconcile_accounts(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    users = _source_rows(source, "users")
    businesses_by_owner: dict[int, list[dict[str, object]]] = defaultdict(list)
    for business in _source_rows(source, "businesses"):
        owner_id = _optional_int(business.get("user_id"))
        if owner_id is not None:
            businesses_by_owner[owner_id].append(business)
    records = [_account_record(user) for user in users]
    conflicts = _identity_conflicts(records)
    counters = {
        "created": 0,
        "reused": 0,
        "updated": 0,
        "quarantined": 0,
        "issues": 0,
    }

    for record in records:
        legacy_id = int(record["legacy_id"])
        conflict_codes = conflicts.get(legacy_id, [])
        if not record["login"]:
            conflict_codes = [*conflict_codes, "identity.login_missing"]
        if conflict_codes:
            counters["quarantined"] += 1
            for code in sorted(set(conflict_codes)):
                counters["issues"] += await _ensure_issue(
                    session,
                    run,
                    entity_type="user_account",
                    legacy_id=legacy_id,
                    issue_code=code,
                )
            await _upsert_mapping(
                session,
                entity_type="user_account",
                legacy_id=legacy_id,
                target_id=None,
                row_hash=source_row_hash("user_account", record),
                mapping_status="quarantined",
                review_reason=sorted(set(conflict_codes))[0],
                run=run,
            )
            continue

        row_hash = source_row_hash("user_account", record)
        account_type = AccountType(str(record["account_type"]))
        existing_mapping = await _find_mapping(
            session,
            "user_account",
            legacy_id,
        )
        mapped = (
            await session.get(Account, existing_mapping.target_id)
            if existing_mapping is not None and existing_mapping.target_id is not None
            else None
        )
        if mapped is not None and mapped.account_type is not account_type:
            mapped = None

        business_rehome: tuple[Account, dict[str, object]] | None = None
        by_login = await _account_by_login(session, str(record["login"]))
        if by_login is not None and by_login.account_type is not account_type:
            rehome_record = await _legacy_business_rehome_record(
                session,
                occupied=by_login,
                user_record=record,
                source_businesses=businesses_by_owner.get(legacy_id, []),
            )
            if rehome_record is not None:
                business_rehome = (by_login, rehome_record)
                by_login = None
            else:
                counters["quarantined"] += 1
                counters["issues"] += await _ensure_issue(
                    session,
                    run,
                    entity_type="user_account",
                    legacy_id=legacy_id,
                    issue_code="identity.account_type_mismatch",
                )
                await _upsert_mapping(
                    session,
                    entity_type="user_account",
                    legacy_id=legacy_id,
                    target_id=None,
                    row_hash=row_hash,
                    mapping_status="quarantined",
                    review_reason="identity.account_type_mismatch",
                    run=run,
                )
                continue

        by_telegram = None
        if record["telegram_user_id"] is not None:
            by_telegram = await _account_by_telegram(
                session,
                int(record["telegram_user_id"]),
                account_type,
            )
        candidates = {
            candidate.id: candidate
            for candidate in (mapped, by_login, by_telegram)
            if candidate is not None
        }
        if len(candidates) > 1:
            counters["quarantined"] += 1
            counters["issues"] += await _ensure_issue(
                session,
                run,
                entity_type="user_account",
                legacy_id=legacy_id,
                issue_code="identity.identifiers_disagree",
            )
            await _upsert_mapping(
                session,
                entity_type="user_account",
                legacy_id=legacy_id,
                target_id=None,
                row_hash=row_hash,
                mapping_status="quarantined",
                review_reason="identity.identifiers_disagree",
                run=run,
            )
            continue

        if business_rehome is not None:
            occupied, business_record = business_rehome
            _apply_account_record(occupied, business_record)
            await session.flush()

        account = next(iter(candidates.values()), None)
        account_created = account is None
        account_changed = False
        if account is None:
            created_at = _unix_datetime(record.get("created_at"))
            account = Account(
                account_type=account_type,
                login=str(record["login"]),
                password_hash=str(record["password_hash"]),
                telegram_user_id=_optional_int(record.get("telegram_user_id")),
                status=str(record["status"]),
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(account)
            await session.flush()
            counters["created"] += 1
        else:
            account_changed = _apply_account_record(account, record)

        counters["issues"] += await _ensure_user_profile(
            session,
            account,
            record,
            run=run,
            legacy_id=legacy_id,
        )
        await _upsert_mapping(
            session,
            entity_type="user_account",
            legacy_id=legacy_id,
            target_id=account.id,
            row_hash=row_hash,
            mapping_status="mapped",
            review_reason="",
            run=run,
        )
        if not account_created:
            if (
                account_changed
                or existing_mapping is None
                or existing_mapping.target_id != account.id
                or existing_mapping.source_row_hash != row_hash
            ):
                counters["updated"] += 1
            else:
                counters["reused"] += 1

    await session.flush()
    return StageResult(**counters)
