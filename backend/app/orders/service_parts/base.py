"""Umumiy asos: bog'liqliklar, egalik tekshiruvi, javob shakli.

`_project` — buyurtmani API javobiga aylantiradi; barcha mixin'lar
shuni ishlatadi, shuning uchun shu yerda.
"""

from __future__ import annotations

import re
from datetime import datetime

from app.cash_register.service_parts import CashRegisterService
from app.catalog.repository import build_content_public_id
from app.core.errors import ApiError
from app.debt_ledger.service import DebtLedgerService
from app.notifications.repository import NotificationRepository
from app.orders.model import Order, OrderItem
from app.orders.repository import OrderRepository
from app.orders.schemas import (
    OrderRead,
)
from app.orders.service_parts.helpers import (
    ImageUrlProvider,
    SessionFactory,
    TaxiOrderLink,
)
from app.outbox.repository import enqueue_event
from app.profiles.model import BusinessProfile, UserProfile
from app.public_discovery.repository import build_listing_public_id, build_public_id
from app.public_discovery.schemas import PublicResultKind


class OrderServiceBase:
    def __init__(
        self,
        session_factory: SessionFactory,
        image_url_provider: ImageUrlProvider,
        *,
        repository: OrderRepository | None = None,
        notification_repository: NotificationRepository | None = None,
        cash_register_service: CashRegisterService | None = None,
        debt_ledger_service: DebtLedgerService | None = None,
        taxi_service: TaxiOrderLink | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._image_url_provider = image_url_provider
        self._repository = repository or OrderRepository()
        self._notification_repository = (
            notification_repository or NotificationRepository()
        )
        self._cash_register_service = cash_register_service
        self._debt_ledger_service = debt_ledger_service
        self._taxi_service = taxi_service

    async def _owned(self, session, order_id: int, account_id: int, lock: bool = False):
        order = await self._repository.owned_order(
            session, order_id=order_id, account_id=account_id, lock=lock
        )
        if order is None:
            raise ApiError(404, "order_not_found", "Buyurtma topilmadi.")
        side = "customer" if order.customer_account_id == account_id else "provider"
        return order, side

    async def _profile(self, session, account_id: int, kind: str):
        model = BusinessProfile if kind == "business" else UserProfile
        return await session.get(model, account_id)

    @staticmethod
    def _price_to_int(value: str) -> int:
        digits = re.sub(r"[^0-9]", "", value or "")
        return int(digits[:12]) if digits else 0

    def _changed(self, order: Order, side: str, event: str, now: datetime) -> None:
        order.last_event = event
        if side == "customer":
            order.customer_seen_at = now
            order.provider_seen_at = None
        else:
            order.provider_seen_at = now
            order.customer_seen_at = None

    async def _event(
        self,
        session,
        topic: str,
        order: Order,
        actor_id: int,
        message_id: int | None = None,
    ):
        payload = {
            "order_id": order.id,
            "actor_account_id": actor_id,
            "status": order.status,
        }
        if message_id is not None:
            payload["message_id"] = message_id
        await enqueue_event(session, topic, payload)

    async def _project(
        self,
        session,
        order: Order,
        side: str,
        *,
        prefetched_items: list[OrderItem] | None = None,
        prefetched_business: BusinessProfile | None = None,
        business_prefetched: bool = False,
        message_summary: dict[str, object] | None = None,
    ) -> OrderRead:
        items = (
            prefetched_items
            if prefetched_items is not None
            else await self._repository.items(session, order.id)
        )
        business = prefetched_business
        if not business_prefetched and order.provider_kind == "business":
            business = await session.get(BusinessProfile, order.provider_account_id)
        if message_summary is None:
            message_summary = (
                await self._repository.message_summaries(session, [order.id])
            ).get(order.id, {})
        customer_kind = (
            PublicResultKind.BUSINESS
            if order.customer_kind == "business"
            else PublicResultKind.USER
        )
        provider_kind = (
            PublicResultKind.BUSINESS
            if order.provider_kind == "business"
            else PublicResultKind.USER
        )
        item_public_id = (
            build_content_public_id(items[0].kind, order.item_id)
            if order.item_id is not None and items
            else ""
        )
        return OrderRead(
            id=order.id,
            view=side,
            title=order.title,
            customer_name=order.customer_name,
            customer_public_id=build_public_id(
                customer_kind, order.customer_account_id
            ),
            provider_name=order.provider_name,
            provider_kind=order.provider_kind,
            order_type=order.order_type,
            provider_public_id=build_public_id(
                provider_kind, order.provider_account_id
            ),
            item_public_id=item_public_id,
            listing_public_id=(
                build_listing_public_id(order.listing_id)
                if order.listing_id is not None
                else ""
            ),
            order_category=order.order_category,
            address=order.address,
            desired_time=order.desired_time,
            delivery_lat=order.delivery_lat,
            delivery_lng=order.delivery_lng,
            note=order.note,
            phone=order.phone,
            qty=float(order.qty),
            total_amount=order.total_amount,
            total_text=(
                f"{order.total_amount:,}".replace(",", " ") + " so'm"
                if order.total_amount > 0
                else ""
            ),
            status=order.status,
            payment_status=order.payment_status,
            pay_type=order.pay_type,
            debtor_id=order.debtor_id,
            receipt_message_id=order.receipt_message_id,
            problem_open=order.problem_open,
            problem_reason=order.problem_reason,
            problem_note=order.problem_note,
            problem_solution=order.problem_solution,
            problem_opened_at=order.problem_opened_at,
            problem_resolved_at=order.problem_resolved_at,
            seller_completed_at=order.seller_completed_at,
            customer_received_at=order.customer_received_at,
            last_event=order.last_event,
            chat_count=int(message_summary.get("chat_count", 0)),
            last_chat=str(message_summary.get("last_chat", "")),
            last_chat_at=message_summary.get("last_chat_at"),
            pay_card=business.pay_card if business else "",
            pay_holder=business.pay_holder if business else "",
            pay_qr_url=self._image_url_provider(business.pay_qr_object_key)
            if business
            else "",
            provider_address=business.address if business else "",
            provider_phone=business.phone if business else order.provider_phone,
            provider_work_hours=business.work_hours if business else {},
            provider_lat=business.latitude if business else None,
            provider_lng=business.longitude if business else None,
            customer_seen_at=order.customer_seen_at,
            provider_seen_at=order.provider_seen_at,
            seen_at=order.provider_seen_at
            if side == "provider"
            else order.customer_seen_at,
            is_unread=(
                order.provider_seen_at is None
                if side == "provider"
                else order.customer_seen_at is None
            ),
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=[
                {
                    "id": item.id,
                    "public_id": build_content_public_id(
                        item.kind, item.catalog_item_id
                    )
                    if item.catalog_item_id
                    else "",
                    "name": item.item_name,
                    "price": item.price_text,
                    "qty": float(item.qty),
                    "unit": item.unit,
                    "line_total": item.line_total,
                    "note": item.note,
                    "kind": item.kind,
                }
                for item in items
            ],
        )
