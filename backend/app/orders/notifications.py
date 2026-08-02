from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.business_online.service import next_record_id, normalized_payload, resource_rows
from app.cabinet_records.dual_write import sync_json_fallback
from app.cabinet_records.repository import CabinetRecordRepository
from app.orders.model import Order
from app.profiles.model import BusinessProfile, UserProfile


def _is_read(row: dict[str, object]) -> bool:
    try:
        return bool(int(row.get("is_read") or 0))
    except (TypeError, ValueError):
        return bool(row.get("is_read"))


async def append_order_notification(
    session: AsyncSession,
    repository: CabinetRecordRepository,
    order: Order,
    *,
    side: str,
    event: str,
    title: str,
    body: str,
    action_type: str = "",
) -> None:
    account_id = (
        order.customer_account_id if side == "customer" else order.provider_account_id
    )
    account_type = order.customer_kind if side == "customer" else order.provider_kind
    profile_type = BusinessProfile if account_type == "business" else UserProfile
    profile = await session.get(profile_type, account_id, with_for_update=True)
    if profile is None:
        return

    payload = normalized_payload(profile.cabinet_payload)
    payload.update(await repository.read_payload(
        session,
        account_id=account_id,
        account_type=account_type,
    ))
    rows = resource_rows(payload, "notifications")
    event_key = f"order:{order.id}:{event}"
    if any(str(row.get("event_key") or "") == event_key for row in rows):
        return
    now = int(datetime.now(UTC).timestamp())
    rows.append({
        "id": next_record_id(rows),
        "event_key": event_key,
        "title": title,
        "body": body,
        "order_id": order.id,
        "action_type": action_type,
        "requires_action": 1 if action_type else 0,
        "is_read": 0,
        "created_at": now,
    })
    payload["notifications"] = rows
    await repository.replace_resource(
        session,
        account_id=account_id,
        account_type=account_type,
        resource="notifications",
        rows=rows,
    )
    sync_json_fallback(profile, payload)
    snapshot = deepcopy(profile.dashboard_snapshot or {})
    snapshot["unread"] = sum(not _is_read(row) for row in rows)
    profile.dashboard_snapshot = snapshot


async def mark_order_notifications_read(
    session: AsyncSession,
    repository: CabinetRecordRepository,
    order: Order,
    *,
    side: str,
) -> None:
    account_id = (
        order.customer_account_id if side == "customer" else order.provider_account_id
    )
    account_type = order.customer_kind if side == "customer" else order.provider_kind
    profile_type = BusinessProfile if account_type == "business" else UserProfile
    profile = await session.get(profile_type, account_id, with_for_update=True)
    if profile is None:
        return
    payload = normalized_payload(profile.cabinet_payload)
    payload.update(await repository.read_payload(
        session,
        account_id=account_id,
        account_type=account_type,
    ))
    rows = resource_rows(payload, "notifications")
    now = int(datetime.now(UTC).timestamp())
    changed = False
    for row in rows:
        if int(row.get("order_id") or 0) != order.id or _is_read(row):
            continue
        row["is_read"] = 1
        row["read_at"] = now
        changed = True
    if not changed:
        return
    payload["notifications"] = rows
    await repository.replace_resource(
        session,
        account_id=account_id,
        account_type=account_type,
        resource="notifications",
        rows=rows,
    )
    sync_json_fallback(profile, payload)
    snapshot = deepcopy(profile.dashboard_snapshot or {})
    snapshot["unread"] = sum(not _is_read(row) for row in rows)
    profile.dashboard_snapshot = snapshot
