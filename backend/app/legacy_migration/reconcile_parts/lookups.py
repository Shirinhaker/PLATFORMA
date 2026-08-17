from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.legacy_migration.model import (
    MigrationRun,
)
from app.legacy_migration.reconcile_parts.helpers import (
    _float_or,
    _optional_float,
    _text,
)
from app.legacy_migration.reconcile_parts.mapping import (
    _ensure_issue,
)
from app.profiles.model import UserProfile


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
            indexes["identity.phone_duplicate"][(account_type, phone)].append(legacy_id)

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
        await session.scalars(select(Account).where(func.lower(Account.login) == login))
    ).one_or_none()


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
