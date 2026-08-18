from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.legacy_migration.reconcile_parts.helpers import (
    _float_or,
    _normalize_phone,
    _optional_float,
    _optional_int,
    _parse_work_hours,
    _text,
)
from app.legacy_migration.reconcile_parts.lookups import (
    _account_by_login,
)
from app.profiles.model import BusinessProfile


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
    if not business_login or business_login == str(user_record["login"]):
        return None

    login_owner = await _account_by_login(session, business_login)
    if login_owner is not None and login_owner.id != occupied.id:
        return None

    return business_record


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
