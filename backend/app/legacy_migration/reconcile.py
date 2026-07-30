from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from math import isfinite
import json
import sqlite3

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.legacy_migration.model import (
    LegacyIdMap,
    MigrationIssue,
    MigrationRun,
)
from app.profiles.model import BusinessProfile, UserProfile


@dataclass(frozen=True)
class StageResult:
    created: int = 0
    reused: int = 0
    updated: int = 0
    quarantined: int = 0
    issues: int = 0


def source_row_hash(
    entity_type: str,
    row: Mapping[str, object],
) -> str:
    payload = {
        "entity_type": entity_type,
        "row": {key: row[key] for key in sorted(row)},
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


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
            if existing_mapping is not None
            and existing_mapping.target_id is not None
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
                telegram_user_id=_optional_int(
                    record.get("telegram_user_id")
                ),
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


async def reconcile_businesses(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    users = {
        int(row["id"]): row
        for row in _source_rows(source, "users")
    }
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
    conflicts = _identity_conflicts(
        [record for _, record in business_records]
    )
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
            if owner_mapping is not None
            and owner_mapping.target_id is not None
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
            if existing_mapping is not None
            and existing_mapping.target_id is not None
            else None
        )
        if mapped is not None and mapped.account_type is not AccountType.BUSINESS:
            mapped = None

        by_login = await _account_by_login(session, str(record["login"]))
        if (
            by_login is not None
            and by_login.account_type is not AccountType.BUSINESS
        ):
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
                telegram_user_id=_optional_int(
                    record.get("telegram_user_id")
                ),
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


def _source_rows(
    source: sqlite3.Connection,
    table: str,
) -> list[dict[str, object]]:
    cursor = source.execute(f'SELECT * FROM "{table}" ORDER BY id')
    names = [description[0] for description in cursor.description]
    return [
        {name: row[index] for index, name in enumerate(names)}
        for row in cursor.fetchall()
    ]


def _account_record(
    user: Mapping[str, object],
) -> dict[str, object]:
    phone = _text(user.get("phone"))
    return {
        **dict(user),
        "legacy_id": int(user["id"]),
        "account_type": AccountType.USER.value,
        "login": _text(user.get("login")).casefold(),
        "password_hash": _text(user.get("pass_hash")),
        "telegram_user_id": _optional_int(user.get("tg_id")),
        "normalized_phone": _normalize_phone(phone),
        "status": _text(user.get("status")) or "active",
    }


def _business_account_record(
    business: Mapping[str, object],
    owner: Mapping[str, object] | None,
) -> dict[str, object]:
    phone = _text(business.get("phone")) or _text((owner or {}).get("phone"))
    return {
        **dict(business),
        "legacy_id": int(business["id"]),
        "account_type": AccountType.BUSINESS.value,
        "login": _text(business.get("biz_login")).casefold(),
        "password_hash": _text(business.get("biz_pass_hash")),
        "telegram_user_id": _optional_int((owner or {}).get("tg_id")),
        "normalized_phone": _normalize_phone(phone),
        "status": _text(business.get("status")) or "active",
    }


def _apply_account_record(
    account: Account,
    record: Mapping[str, object],
) -> bool:
    values = {
        "login": str(record["login"]),
        "telegram_user_id": _optional_int(record.get("telegram_user_id")),
        "status": str(record["status"]),
    }
    password_hash = str(record["password_hash"])
    if password_hash:
        values["password_hash"] = password_hash
    changed = False
    for field, value in values.items():
        if getattr(account, field) == value:
            continue
        setattr(account, field, value)
        changed = True
    if changed:
        account.updated_at = datetime.now(UTC)
    return changed


def _identity_conflicts(
    records: list[dict[str, object]],
) -> dict[int, list[str]]:
    indexes: dict[str, dict[object, list[int]]] = {
        "identity.login_duplicate": defaultdict(list),
        "identity.telegram_duplicate": defaultdict(list),
        "identity.phone_duplicate": defaultdict(list),
    }
    for record in records:
        legacy_id = int(record["legacy_id"])
        account_type = str(record["account_type"])
        login = str(record["login"])
        if login:
            indexes["identity.login_duplicate"][login].append(legacy_id)
        telegram = record.get("telegram_user_id")
        if telegram is not None:
            indexes["identity.telegram_duplicate"][
                (account_type, int(telegram))
            ].append(legacy_id)
        phone = str(record.get("normalized_phone") or "")
        if phone:
            indexes["identity.phone_duplicate"][
                (account_type, phone)
            ].append(legacy_id)

    conflicts: dict[int, list[str]] = defaultdict(list)
    for code, values in indexes.items():
        for legacy_ids in values.values():
            if len(legacy_ids) <= 1:
                continue
            for legacy_id in legacy_ids:
                conflicts[legacy_id].append(code)
    return conflicts


async def _account_by_login(
    session: AsyncSession,
    login: str,
) -> Account | None:
    return (
        await session.scalars(
            select(Account).where(func.lower(Account.login) == login)
        )
    ).one_or_none()


async def _legacy_business_rehome_record(
    session: AsyncSession,
    *,
    occupied: Account,
    user_record: Mapping[str, object],
    source_businesses: list[dict[str, object]],
) -> dict[str, object] | None:
    telegram_user_id = _optional_int(user_record.get("telegram_user_id"))
    if (
        occupied.account_type is not AccountType.BUSINESS
        or telegram_user_id is None
        or occupied.telegram_user_id != telegram_user_id
        or len(source_businesses) != 1
        or await session.get(BusinessProfile, occupied.id) is None
    ):
        return None

    business_record = _business_account_record(
        source_businesses[0],
        user_record,
    )
    business_login = str(business_record["login"])
    if (
        not business_login
        or business_login == str(user_record["login"])
    ):
        return None

    login_owner = await _account_by_login(session, business_login)
    if login_owner is not None and login_owner.id != occupied.id:
        return None

    return business_record


async def _account_by_telegram(
    session: AsyncSession,
    telegram_user_id: int,
    account_type: AccountType,
) -> Account | None:
    return (
        await session.scalars(
            select(Account).where(
                Account.telegram_user_id == telegram_user_id,
                Account.account_type == account_type,
            )
        )
    ).one_or_none()


async def _find_mapping(
    session: AsyncSession,
    entity_type: str,
    legacy_id: int,
) -> LegacyIdMap | None:
    return (
        await session.scalars(
            select(LegacyIdMap).where(
                LegacyIdMap.entity_type == entity_type,
                LegacyIdMap.legacy_id == legacy_id,
            )
        )
    ).one_or_none()


async def _upsert_mapping(
    session: AsyncSession,
    *,
    entity_type: str,
    legacy_id: int,
    target_id: int | None,
    row_hash: str,
    mapping_status: str,
    review_reason: str,
    run: MigrationRun,
) -> LegacyIdMap:
    mapping = await _find_mapping(session, entity_type, legacy_id)
    if mapping is None:
        mapping = LegacyIdMap(
            entity_type=entity_type,
            legacy_id=legacy_id,
            target_id=target_id,
            source_row_hash=row_hash,
            mapping_status=mapping_status,
            review_reason=review_reason,
            last_run_id=run.id,
        )
        session.add(mapping)
    else:
        mapping.target_id = target_id
        mapping.source_row_hash = row_hash
        mapping.mapping_status = mapping_status
        mapping.review_reason = review_reason
        mapping.last_run_id = run.id
    await session.flush()
    return mapping


async def _ensure_issue(
    session: AsyncSession,
    run: MigrationRun,
    *,
    entity_type: str,
    legacy_id: int,
    issue_code: str,
) -> int:
    existing = (
        await session.scalars(
            select(MigrationIssue).where(
                MigrationIssue.migration_run_id == run.id,
                MigrationIssue.entity_type == entity_type,
                MigrationIssue.legacy_id == legacy_id,
                MigrationIssue.issue_code == issue_code,
            )
        )
    ).one_or_none()
    if existing is not None:
        return 0
    session.add(
        MigrationIssue(
            migration_run_id=run.id,
            entity_type=entity_type,
            legacy_id=legacy_id,
            issue_code=issue_code,
            details_json={},
            resolved=False,
            created_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return 1


async def _ensure_user_profile(
    session: AsyncSession,
    account: Account,
    record: Mapping[str, object],
    *,
    run: MigrationRun,
    legacy_id: int,
) -> int:
    if account.account_type is not AccountType.USER:
        return 0
    profile = await session.get(UserProfile, account.id)
    values = {
        "name": _text(record.get("name")),
        "phone": _text(record.get("phone")),
        "public_username": _text(record.get("username")).lstrip("@"),
        "region": _text(record.get("region")),
        "district": _text(record.get("district")),
        "mahalla": _text(record.get("mahalla")),
        "latitude": _optional_float(record.get("lat")),
        "longitude": _optional_float(record.get("lng")),
        "location_exact": bool(record.get("location_exact") or False),
        "avatar_object_key": "",
        "avatar_x": _float_or(record.get("avatar_x"), 50.0),
        "avatar_y": _float_or(record.get("avatar_y"), 50.0),
        "avatar_zoom": _float_or(record.get("avatar_zoom"), 1.0),
    }
    issues = 0
    conflicting_account_id = await _profile_username_owner(
        session,
        UserProfile,
        account_id=account.id,
        public_username=str(values["public_username"]),
    )
    if conflicting_account_id is not None:
        values["public_username"] = ""
        issues += await _ensure_issue(
            session,
            run,
            entity_type="user_profile",
            legacy_id=legacy_id,
            issue_code="profile.public_username_conflict",
        )
    if profile is None:
        session.add(UserProfile(account_id=account.id, **values))
    else:
        for field, value in values.items():
            setattr(profile, field, value)
    await session.flush()
    return issues


async def _profile_username_owner(
    session: AsyncSession,
    model,
    *,
    account_id: int,
    public_username: str,
) -> int | None:
    normalized = public_username.lower()
    if not normalized:
        return None
    return await session.scalar(
        select(model.account_id)
        .where(
            func.lower(model.public_username) == normalized,
            model.account_id != account_id,
        )
        .limit(1)
    )


def _business_profile_values(
    row: Mapping[str, object],
) -> dict[str, object]:
    return {
        "name": _text(row.get("name")),
        "phone": _text(row.get("phone")),
        "description": _text(row.get("descr")),
        "public_username": _text(row.get("username")).lstrip("@"),
        "direction": _text(row.get("yon")),
        "activity_type": _text(row.get("tur")),
        "address": _text(row.get("address")),
        "latitude": _optional_float(row.get("lat")),
        "longitude": _optional_float(row.get("lng")),
        "work_hours": _parse_work_hours(row.get("work_hours")),
        "pay_card": _text(row.get("pay_card")),
        "pay_holder": _text(row.get("pay_holder")),
        "pay_qr_object_key": "",
        "director": _text(row.get("director")),
        "tax_id": _text(row.get("inn")),
        "logo_object_key": "",
        "logo_x": _float_or(row.get("logo_x"), 50.0),
        "logo_y": _float_or(row.get("logo_y"), 50.0),
        "logo_zoom": _float_or(row.get("logo_zoom"), 1.0),
    }


def _parse_work_hours(value: object) -> dict[str, object]:
    text = _text(value)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"raw": text}
    return parsed if isinstance(parsed, dict) else {"raw": text}


def _normalize_phone(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def _float_or(value: object, default: float) -> float:
    parsed = _optional_float(value)
    return default if parsed is None else parsed


def _unix_datetime(value: object) -> datetime:
    timestamp = _optional_int(value)
    if timestamp is None:
        return datetime.now(UTC)
    return datetime.fromtimestamp(timestamp, tz=UTC)
