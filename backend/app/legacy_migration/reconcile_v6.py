import sqlite3

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.legacy_migration.model import MigrationRun
from app.legacy_migration.reconcile import (
    StageResult,
    _account_record,
    _apply_account_record,
    _business_account_record,
    _business_profile_values,
    _ensure_user_profile,
    _find_mapping,
    _optional_int,
    _source_rows,
    _text,
    _unix_datetime,
    _upsert_mapping,
    reconcile_accounts as reconcile_accounts_v5,
    reconcile_businesses as reconcile_businesses_v5,
    source_row_hash,
)
from app.profiles.model import BusinessProfile


async def reconcile_accounts(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    pairs = await _shared_login_pairs(session, source)
    counters = _counters()

    for owner_id, business_id, occupied in pairs:
        user_row = _row_by_id(source, "users", owner_id)
        record = _account_record(user_row)
        existing = await _account_by_login_and_type(
            session,
            str(record["login"]),
            AccountType.USER,
        )
        created = existing is None
        if existing is None:
            created_at = _unix_datetime(record.get("created_at"))
            existing = Account(
                account_type=AccountType.USER,
                login=str(record["login"]),
                password_hash=str(record["password_hash"]),
                telegram_user_id=None,
                status=str(record["status"]),
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(existing)
            await session.flush()
        else:
            _apply_account_record(existing, record)

        counters["issues"] += await _ensure_user_profile(
            session,
            existing,
            record,
            run=run,
            legacy_id=owner_id,
        )
        await _upsert_mapping(
            session,
            entity_type="user_account",
            legacy_id=owner_id,
            target_id=existing.id,
            row_hash=source_row_hash("user_account", record),
            mapping_status="mapped",
            review_reason="",
            run=run,
        )
        counters["created" if created else "updated"] += 1

        business_mapping = await _find_mapping(
            session,
            "business_account",
            business_id,
        )
        if business_mapping is not None:
            business_mapping.target_id = occupied.id
            business_mapping.mapping_status = "mapped"
            business_mapping.review_reason = ""
            business_mapping.last_run_id = run.id

    filtered = _filtered_source(source, {pair[0] for pair in pairs}, set())
    try:
        ordinary = await reconcile_accounts_v5(session, filtered, run)
    finally:
        filtered.close()
    return _combine(StageResult(**counters), ordinary)


async def reconcile_businesses(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    pairs = await _shared_login_pairs(session, source)
    counters = _counters()

    for owner_id, business_id, occupied in pairs:
        user_row = _row_by_id(source, "users", owner_id)
        business_row = _row_by_id(source, "businesses", business_id)
        record = _business_account_record(business_row, user_row)
        record["login"] = _text(user_row.get("login")).casefold()
        record["password_hash"] = _text(user_row.get("pass_hash"))
        _apply_account_record(occupied, record)

        profile = await session.get(BusinessProfile, occupied.id)
        values = _business_profile_values(business_row)
        if profile is None:
            profile = BusinessProfile(account_id=occupied.id, **values)
            session.add(profile)
            counters["created"] += 1
        else:
            for field, value in values.items():
                setattr(profile, field, value)
            counters["updated"] += 1

        await _upsert_mapping(
            session,
            entity_type="business_account",
            legacy_id=business_id,
            target_id=occupied.id,
            row_hash=source_row_hash("business_account", record),
            mapping_status="mapped",
            review_reason="",
            run=run,
        )

    filtered = _filtered_source(source, set(), {pair[1] for pair in pairs})
    try:
        ordinary = await reconcile_businesses_v5(session, filtered, run)
    finally:
        filtered.close()
    return _combine(StageResult(**counters), ordinary)


async def _shared_login_pairs(
    session: AsyncSession,
    source: sqlite3.Connection,
) -> list[tuple[int, int, Account]]:
    businesses_by_owner: dict[int, list[dict[str, object]]] = {}
    for business in _source_rows(source, "businesses"):
        owner_id = _optional_int(business.get("user_id"))
        if owner_id is not None:
            businesses_by_owner.setdefault(owner_id, []).append(business)

    pairs: list[tuple[int, int, Account]] = []
    for user in _source_rows(source, "users"):
        owner_id = int(user["id"])
        businesses = businesses_by_owner.get(owner_id, [])
        if (
            len(businesses) != 1
            or _optional_int(user.get("tg_id")) is not None
            or _text(businesses[0].get("biz_login"))
            or not _text(user.get("login"))
        ):
            continue
        occupied = await _account_by_login_and_type(
            session,
            _text(user.get("login")).casefold(),
            AccountType.BUSINESS,
        )
        if occupied is None:
            continue
        if await session.get(BusinessProfile, occupied.id) is None:
            continue
        pairs.append((owner_id, int(businesses[0]["id"]), occupied))
    return pairs


async def _account_by_login_and_type(
    session: AsyncSession,
    login: str,
    account_type: AccountType,
) -> Account | None:
    return (
        await session.scalars(
            select(Account).where(
                func.lower(Account.login) == login,
                Account.account_type == account_type,
            )
        )
    ).one_or_none()


def _row_by_id(
    source: sqlite3.Connection,
    table: str,
    legacy_id: int,
) -> dict[str, object]:
    return next(
        row for row in _source_rows(source, table) if int(row["id"]) == legacy_id
    )


def _filtered_source(
    source: sqlite3.Connection,
    excluded_users: set[int],
    excluded_businesses: set[int],
) -> sqlite3.Connection:
    target = sqlite3.connect(":memory:")
    source.backup(target)
    if excluded_users:
        placeholders = ",".join("?" for _ in excluded_users)
        target.execute(
            f"DELETE FROM users WHERE id IN ({placeholders})",
            tuple(sorted(excluded_users)),
        )
    if excluded_businesses:
        placeholders = ",".join("?" for _ in excluded_businesses)
        target.execute(
            f"DELETE FROM businesses WHERE id IN ({placeholders})",
            tuple(sorted(excluded_businesses)),
        )
    target.commit()
    target.row_factory = sqlite3.Row
    return target


def _counters() -> dict[str, int]:
    return {
        "created": 0,
        "reused": 0,
        "updated": 0,
        "quarantined": 0,
        "issues": 0,
    }


def _combine(first: StageResult, second: StageResult) -> StageResult:
    return StageResult(
        created=first.created + second.created,
        reused=first.reused + second.reused,
        updated=first.updated + second.updated,
        quarantined=first.quarantined + second.quarantined,
        issues=first.issues + second.issues,
    )
