from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.repository import NotificationRepository
from app.orders.model import Order


async def append_order_notification(
    session: AsyncSession,
    repository: NotificationRepository,
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
    event_key = f"order:{order.id}:{event}"
    now = int(datetime.now(UTC).timestamp())
    await repository.append(
        session,
        account_id=account_id,
        account_type=account_type,
        row={
            "event_key": event_key,
            "title": title,
            "body": body,
            "order_id": order.id,
            "action_type": action_type,
            "requires_action": 1 if action_type else 0,
            "is_read": 0,
            "created_at": now,
        },
    )


async def mark_order_notifications_read(
    session: AsyncSession,
    repository: NotificationRepository,
    order: Order,
    *,
    side: str,
) -> None:
    account_id = (
        order.customer_account_id if side == "customer" else order.provider_account_id
    )
    account_type = order.customer_kind if side == "customer" else order.provider_kind
    await repository.mark_order_read(
        session,
        account_id=account_id,
        account_type=account_type,
        order_id=order.id,
        read_at=int(datetime.now(UTC).timestamp()),
    )
