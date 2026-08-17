from __future__ import annotations

import sqlite3
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.legacy_migration.model import MigrationRun
from app.legacy_migration.parity_v7.entry import (
    reconcile_accounts as reconcile_accounts_v7,
)
from app.legacy_migration.parity_v7.entry import (
    reconcile_businesses as reconcile_businesses_v7,
)
from app.legacy_migration.reconcile_parts.constants import StageResult
from app.legacy_migration.reconcile_parts.mapping import _find_mapping
from app.profiles.model import BusinessProfile, UserProfile

# static/index.html v1656: orderIsActive()
V1656_ACTIVE_ORDER_STATUSES = frozenset(
    {
        "new",
        "accepted",
        "preparing",
        "tayyor",
        "courier_assigned",
        "courier_arrived_store",
        "handoff_waiting_seller",
        "in_delivery",
        "courier_arrived_customer",
        "delivered_waiting_customer",
        "pickup_waiting_customer",
    }
)


def _integer(value: object, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _boolean(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


def _source_ids(source: sqlite3.Connection, table: str) -> list[int]:
    try:
        return [
            int(row[0])
            for row in source.execute(
                f'SELECT id FROM "{table}" ORDER BY id'
            ).fetchall()
        ]
    except sqlite3.Error:
        return []


def v1656_order_is_active(row: dict[str, Any]) -> bool:
    return (
        not _boolean(row.get("problem_open"))
        and str(row.get("status") or "") in V1656_ACTIVE_ORDER_STATUSES
    )


def _user_notification_visible(
    row: dict[str, Any],
    *,
    legacy_user_id: int,
) -> bool:
    # v1656 /api/notifications?actor_type=user aynan user actorini ajratadi.
    # Juda eski qatorda actor maydonlari bo'lmasa, userga tegishli deb qolamiz.
    actor_kind = str(row.get("actor_kind") or "").strip().casefold()
    if actor_kind and actor_kind != "user":
        return False
    actor_id = _integer(row.get("actor_id"))
    if actor_kind == "user" and actor_id and actor_id != legacy_user_id:
        return False
    return True


def _unread(row: dict[str, Any]) -> bool:
    return not _boolean(row.get("is_read")) and not _boolean(row.get("resolved_at"))


async def _remember_profile_media(
    session: AsyncSession,
    source: sqlite3.Connection,
    *,
    source_table: str,
    mapping_type: str,
    model,
    field: str,
) -> dict[int, str]:
    remembered: dict[int, str] = {}
    for legacy_id in _source_ids(source, source_table):
        mapping = await _find_mapping(session, mapping_type, legacy_id)
        if mapping is None or mapping.target_id is None:
            continue
        profile = await session.get(model, mapping.target_id)
        if profile is None:
            continue
        object_key = str(getattr(profile, field, "") or "")
        if object_key:
            remembered[int(mapping.target_id)] = object_key
    return remembered


async def _restore_profile_media(
    session: AsyncSession,
    remembered: dict[int, str],
    *,
    model,
    field: str,
) -> None:
    for account_id, object_key in remembered.items():
        profile = await session.get(model, account_id)
        if profile is not None:
            setattr(profile, field, object_key)


async def reconcile_accounts(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    """V8 account import + v1656 user-cabinet hisoblari.

    V7/V6 importi barcha kabinet ma'lumotlarini ko'chiradi. Uning eski
    dashboard hisobida esa "terminal bo'lmagan har qanday status" faol deb
    sanalgan va user notification payloadiga shu owner user_id dagi business
    actor xabarlari ham kirgan. v1656 ikkalasini ham actor/status bo'yicha
    aniq filtrlardi. Shu wrapper import tugagach aynan v1656 semantikasini
    tiklaydi; qolgan account migratsiyasiga tegmaydi.

    Idempotent va production passlarda reconcile eski source'dagi
    avatar_file qiymatini object-key deb ishlata olmaydi va profile modeldagi
    kalitni bo'shatadi. Late V8 profil-media ko'chirishidan keyin mavjud R2
    object-keyni shu sabab oldindan eslab, reconcile tugagach qaytaramiz.
    """
    avatar_keys = await _remember_profile_media(
        session,
        source,
        source_table="users",
        mapping_type="user_account",
        model=UserProfile,
        field="avatar_object_key",
    )
    result = await reconcile_accounts_v7(session, source, run)
    await repair_user_cabinet_parity(session, source)
    await _restore_profile_media(
        session,
        avatar_keys,
        model=UserProfile,
        field="avatar_object_key",
    )
    await session.flush()
    return result


async def reconcile_businesses(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    """Business importni o'zgartirmay, ko'chirilgan v1656 logoni saqla."""
    logo_keys = await _remember_profile_media(
        session,
        source,
        source_table="businesses",
        mapping_type="business_account",
        model=BusinessProfile,
        field="logo_object_key",
    )
    result = await reconcile_businesses_v7(session, source, run)
    await _restore_profile_media(
        session,
        logo_keys,
        model=BusinessProfile,
        field="logo_object_key",
    )
    await session.flush()
    return result


async def repair_user_cabinet_parity(
    session: AsyncSession,
    source: sqlite3.Connection,
) -> None:
    for legacy_user_id in _source_ids(source, "users"):
        mapping = await _find_mapping(
            session,
            "user_account",
            legacy_user_id,
        )
        if mapping is None or mapping.target_id is None:
            continue
        profile = await session.get(UserProfile, mapping.target_id)
        if profile is None:
            continue

        payload = dict(profile.cabinet_payload or {})
        orders = (
            [row for row in payload.get("orders", []) if isinstance(row, dict)]
            if isinstance(payload.get("orders"), list)
            else []
        )
        saved = (
            [row for row in payload.get("saved", []) if isinstance(row, dict)]
            if isinstance(payload.get("saved"), list)
            else []
        )
        notifications = (
            [
                row
                for row in payload.get("notifications", [])
                if isinstance(row, dict)
                and _user_notification_visible(
                    row,
                    legacy_user_id=legacy_user_id,
                )
            ]
            if isinstance(payload.get("notifications"), list)
            else []
        )

        # 0011_notifications_relational aynan shu tozalangan payloaddan user
        # notificationlarini alohida jadvalga o'tkazadi. Business actor xabari
        # business profil payloadida qoladi; user kabinetga ikkinchi marta kirmaydi.
        payload["notifications"] = notifications
        profile.cabinet_payload = payload

        snapshot = dict(profile.dashboard_snapshot or {})
        snapshot.update(
            {
                "active_orders": sum(v1656_order_is_active(row) for row in orders),
                "following": int(profile.following_count or 0),
                "saved": len(saved),
                "unread": sum(_unread(row) for row in notifications),
                "followers": int(profile.followers_count or 0),
            }
        )
        profile.dashboard_snapshot = snapshot
