from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.model import CatalogItem
from app.legacy_migration.model import OwnerState, ReviewState
from app.orders.model import Order, OrderItem, OrderMessage


class OrderRepository:
    async def all_catalog_items(self, session: AsyncSession) -> list[CatalogItem]:
        return list((await session.scalars(
            select(CatalogItem).where(
                CatalogItem.status == "active",
                CatalogItem.review_state == ReviewState.READY,
                CatalogItem.owner_state == OwnerState.LINKED,
            )
        )).all())

    async def owned_order(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        account_id: int,
        lock: bool = False,
    ) -> Order | None:
        statement = select(Order).where(
            Order.id == order_id,
            (Order.customer_account_id == account_id)
            | (Order.provider_account_id == account_id),
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def list_for_side(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        side: str,
    ) -> list[Order]:
        owner = (
            Order.customer_account_id
            if side == "customer"
            else Order.provider_account_id
        )
        return list((await session.scalars(
            select(Order)
            .where(owner == account_id)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .limit(200)
        )).all())

    async def items(self, session: AsyncSession, order_id: int) -> list[OrderItem]:
        return list((await session.scalars(
            select(OrderItem)
            .where(OrderItem.order_id == order_id)
            .order_by(OrderItem.id)
        )).all())

    async def items_for_orders(
        self, session: AsyncSession, order_ids: list[int]
    ) -> dict[int, list[OrderItem]]:
        if not order_ids:
            return {}
        rows = list((await session.scalars(
            select(OrderItem)
            .where(OrderItem.order_id.in_(order_ids))
            .order_by(OrderItem.order_id, OrderItem.id)
        )).all())
        grouped: dict[int, list[OrderItem]] = {order_id: [] for order_id in order_ids}
        for row in rows:
            grouped.setdefault(row.order_id, []).append(row)
        return grouped

    async def messages(
        self, session: AsyncSession, order_id: int
    ) -> list[OrderMessage]:
        return list((await session.scalars(
            select(OrderMessage)
            .where(OrderMessage.order_id == order_id)
            .order_by(OrderMessage.created_at, OrderMessage.id)
            .limit(500)
        )).all())

    async def message_summaries(
        self, session: AsyncSession, order_ids: list[int]
    ) -> dict[int, dict[str, object]]:
        if not order_ids:
            return {}
        counts = (await session.execute(
            select(OrderMessage.order_id, func.count(OrderMessage.id))
            .where(OrderMessage.order_id.in_(order_ids))
            .group_by(OrderMessage.order_id)
        )).all()
        ranked = select(
            OrderMessage.order_id.label("order_id"),
            OrderMessage.text.label("text"),
            OrderMessage.media_type.label("media_type"),
            OrderMessage.created_at.label("created_at"),
            func.row_number().over(
                partition_by=OrderMessage.order_id,
                order_by=(OrderMessage.created_at.desc(), OrderMessage.id.desc()),
            ).label("message_rank"),
        ).where(
            OrderMessage.order_id.in_(order_ids),
            OrderMessage.is_deleted.is_(False),
        ).subquery()
        latest = (await session.execute(
            select(
                ranked.c.order_id,
                ranked.c.text,
                ranked.c.media_type,
                ranked.c.created_at,
            ).where(ranked.c.message_rank == 1)
        )).all()
        summaries: dict[int, dict[str, object]] = {
            int(order_id): {
                "chat_count": int(count),
                "last_chat": "",
                "last_chat_at": None,
            }
            for order_id, count in counts
        }
        for order_id, message, media_type, created_at in latest:
            summary = summaries.setdefault(int(order_id), {"chat_count": 0})
            summary["last_chat"] = message or ("📷 Rasm" if media_type == "photo" else "")
            summary["last_chat_at"] = created_at
        return summaries

    async def message(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        message_id: int,
        lock: bool = False,
    ) -> OrderMessage | None:
        statement = select(OrderMessage).where(
            OrderMessage.id == message_id,
            OrderMessage.order_id == order_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def latest_receipt(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        sender_account_id: int,
    ) -> OrderMessage | None:
        return await session.scalar(
            select(OrderMessage)
            .where(
                OrderMessage.order_id == order_id,
                OrderMessage.sender_account_id == sender_account_id,
                OrderMessage.media_type == "photo",
                OrderMessage.is_deleted.is_(False),
                or_(
                    OrderMessage.media_object_key != "",
                    OrderMessage.legacy_media_url != "",
                ),
            )
            .order_by(OrderMessage.id.desc())
            .limit(1)
        )
