"""Ro'yxatlar: mening buyurtmalarim, kiruvchi qutisi, ko'rildi."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.orders.notifications import (
    mark_order_notifications_read,
)
from app.orders.schemas import (
    OrderRead,
)
from app.orders.service_parts.base import OrderServiceBase
from app.profiles.model import BusinessProfile


class ListingMixin(OrderServiceBase):
    async def list_my(
        self, *, account_id: int, account_type: AccountType
    ) -> list[OrderRead]:
        return await self._list(account_id, "customer")

    async def list_inbox(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        allowed_categories: frozenset[str] | None = None,
    ) -> list[OrderRead]:
        return await self._list(
            account_id,
            "provider",
            allowed_categories=allowed_categories,
        )

    async def assert_staff_provider_access(
        self,
        *,
        order_id: int,
        account_id: int,
        allowed_categories: frozenset[str],
    ) -> None:
        async with self._session_factory() as session:
            order = await self._repository.owned_order(
                session,
                order_id=order_id,
                account_id=account_id,
            )
            allowed = (
                order is not None
                and order.provider_account_id == account_id
                and order.order_category in allowed_categories
            )
            await session.rollback()
            if not allowed:
                raise ApiError(
                    403,
                    "staff_order_forbidden",
                    "Bu buyurtmaga vakolatingiz yo‘q.",
                )

    async def mark_seen(
        self, *, order_id: int, account_id: int, account_type: AccountType
    ) -> OrderRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            now = datetime.now(UTC)
            if side == "customer":
                order.customer_seen_at = now
            else:
                order.provider_seen_at = now
            await mark_order_notifications_read(
                session,
                self._notification_repository,
                order,
                side=side,
            )
            await session.commit()
            return await self._project(session, order, side)

    async def _list(
        self,
        account_id: int,
        side: str,
        *,
        allowed_categories: frozenset[str] | None = None,
    ) -> list[OrderRead]:
        async with self._session_factory() as session:
            rows = await self._repository.list_for_side(
                session,
                account_id=account_id,
                side=side,
                allowed_categories=allowed_categories,
            )
            items_by_order = await self._repository.items_for_orders(
                session, [row.id for row in rows]
            )
            chat_by_order = await self._repository.message_summaries(
                session, [row.id for row in rows]
            )
            business_ids = {
                row.provider_account_id
                for row in rows
                if row.provider_kind == "business"
            }
            businesses = (
                {
                    row.account_id: row
                    for row in list(
                        (
                            await session.scalars(
                                select(BusinessProfile).where(
                                    BusinessProfile.account_id.in_(business_ids)
                                )
                            )
                        ).all()
                    )
                }
                if business_ids
                else {}
            )
            result = [
                await self._project(
                    session,
                    row,
                    side,
                    prefetched_items=items_by_order.get(row.id, []),
                    prefetched_business=businesses.get(row.provider_account_id),
                    business_prefetched=True,
                    message_summary=chat_by_order.get(row.id),
                )
                for row in rows
            ]
            await session.rollback()
            return result
