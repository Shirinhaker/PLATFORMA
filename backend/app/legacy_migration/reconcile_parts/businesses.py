"""Biznes akkauntlari va profillari."""

from __future__ import annotations

import sqlite3

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
    _identity_conflicts,
    _profile_username_owner,
)
from app.legacy_migration.reconcile_parts.mapping import (
    _ensure_issue,
    _find_mapping,
    _upsert_mapping,
)
from app.legacy_migration.reconcile_parts.records import (
    _apply_account_record,
    _business_account_record,
    _business_profile_values,
)
from app.legacy_migration.reconcile_parts.source import (
    _source_rows,
)
from app.profiles.model import BusinessProfile


async def reconcile_businesses(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    users = {int(row["id"]): row for row in _source_rows(source, "users")}
    business_records = [
        (
            row,
            _business_account_record(
                row,
                users.get(int(row.get("user_id") or 0)),
            ),
        )
        for row in _source_rows(source, "businesses")
    ]
    conflicts = _identity_conflicts([record for _, record in business_records])
    counters = {
        "created": 0,
        "reused": 0,
        "updated": 0,
        "quarantined": 0,
        "issues": 0,
    }
    for row, record in business_records:
        legacy_id = int(row["id"])
        owner_legacy_id = int(row.get("user_id") or 0)
        source_owner = users.get(owner_legacy_id)
        row_hash = source_row_hash("business_account", record)
        owner_mapping = await _find_mapping(
            session,
            "user_account",
            owner_legacy_id,
        )
        user_account = (
            await session.get(Account, owner_mapping.target_id)
            if owner_mapping is not None and owner_mapping.target_id is not None
            else None
        )
        if (
            source_owner is None
            or user_account is None
            or user_account.account_type is not AccountType.USER
        ):
            counters["quarantined"] += 1
            counters["issues"] += await _ensure_issue(
                session,
                run,
                entity_type="business_account",
                legacy_id=legacy_id,
                issue_code="identity.business_owner_unresolved",
            )
            await _upsert_mapping(
                session,
                entity_type="business_account",
                legacy_id=legacy_id,
                target_id=None,
                row_hash=row_hash,
                mapping_status="quarantined",
                review_reason="identity.business_owner_unresolved",
                run=run,
            )
            continue

        conflict_codes = conflicts.get(legacy_id, [])
        if not record["login"]:
            conflict_codes = [*conflict_codes, "identity.login_missing"]
        if conflict_codes:
            counters["quarantined"] += 1
            for code in sorted(set(conflict_codes)):
                counters["issues"] += await _ensure_issue(
                    session,
                    run,
                    entity_type="business_account",
                    legacy_id=legacy_id,
                    issue_code=code,
                )
            await _upsert_mapping(
                session,
                entity_type="business_account",
                legacy_id=legacy_id,
                target_id=None,
                row_hash=row_hash,
                mapping_status="quarantined",
                review_reason=sorted(set(conflict_codes))[0],
                run=run,
            )
            continue

        existing_mapping = await _find_mapping(
            session,
            "business_account",
            legacy_id,
        )
        mapped = (
            await session.get(Account, existing_mapping.target_id)
            if existing_mapping is not None and existing_mapping.target_id is not None
            else None
        )
        if mapped is not None and mapped.account_type is not AccountType.BUSINESS:
            mapped = None

        by_login = await _account_by_login(session, str(record["login"]))
        if by_login is not None and by_login.account_type is not AccountType.BUSINESS:
            counters["quarantined"] += 1
            counters["issues"] += await _ensure_issue(
                session,
                run,
                entity_type="business_account",
                legacy_id=legacy_id,
                issue_code="identity.account_type_mismatch",
            )
            await _upsert_mapping(
                session,
                entity_type="business_account",
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
                AccountType.BUSINESS,
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
                entity_type="business_account",
                legacy_id=legacy_id,
                issue_code="identity.identifiers_disagree",
            )
            await _upsert_mapping(
                session,
                entity_type="business_account",
                legacy_id=legacy_id,
                target_id=None,
                row_hash=row_hash,
                mapping_status="quarantined",
                review_reason="identity.identifiers_disagree",
                run=run,
            )
            continue

        account = next(iter(candidates.values()), None)
        account_created = account is None
        if account is None:
            created_at = _unix_datetime(record.get("created_at"))
            account = Account(
                account_type=AccountType.BUSINESS,
                login=str(record["login"]),
                password_hash=str(record["password_hash"]),
                telegram_user_id=_optional_int(record.get("telegram_user_id")),
                status=str(record["status"]),
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(account)
            await session.flush()
        else:
            _apply_account_record(account, record)

        profile = await session.get(BusinessProfile, account.id)
        profile_values = _business_profile_values(row)
        conflicting_account_id = await _profile_username_owner(
            session,
            BusinessProfile,
            account_id=account.id,
            public_username=str(profile_values["public_username"]),
        )
        if conflicting_account_id is not None:
            profile_values["public_username"] = ""
            counters["issues"] += await _ensure_issue(
                session,
                run,
                entity_type="business_profile",
                legacy_id=legacy_id,
                issue_code="profile.public_username_conflict",
            )
        if profile is None:
            profile = BusinessProfile(
                account_id=account.id,
                **profile_values,
            )
            session.add(profile)
            counters["created"] += 1
        elif (
            not account_created
            and existing_mapping is not None
            and existing_mapping.target_id == account.id
            and existing_mapping.source_row_hash == row_hash
        ):
            counters["reused"] += 1
        else:
            for field, value in profile_values.items():
                setattr(profile, field, value)
            counters["updated"] += 1

        await _upsert_mapping(
            session,
            entity_type="business_account",
            legacy_id=legacy_id,
            target_id=account.id,
            row_hash=row_hash,
            mapping_status="mapped",
            review_reason="",
            run=run,
        )

    await session.flush()
    return StageResult(**counters)
