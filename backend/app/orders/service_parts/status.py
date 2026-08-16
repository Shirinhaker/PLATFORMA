"""Holat o'zgarishi: qabul, tayyor, topshirish, olindi."""

from __future__ import annotations

from datetime import UTC, datetime

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.orders.notifications import (
    append_order_notification,
)
from app.orders.schemas import (
    OrderRead,
    OrderStatusChange,
)
from app.orders.service_parts.base import OrderServiceBase
from app.orders.status import validate_status_change


class StatusMixin(OrderServiceBase):
    async def change_status(
        self,
        *,
        order_id: int,
        account_id: int,
        account_type: AccountType,
        body: OrderStatusChange,
    ) -> OrderRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            validate_status_change(
                current=order.status, requested=body.status, side=side
            )
            if body.status == "tayyor":
                if order.problem_open:
                    raise ApiError(
                        409,
                        "order_problem_open",
                        "Muammoli buyurtmani tayyorlash yoki yakunlash mumkin emas. "
                        "Avval to'lov muammosini hal qiling.",
                    )
                if order.payment_status != "confirmed":
                    raise ApiError(
                        409,
                        "order_payment_not_confirmed",
                        "To'lov tasdiqlanmaguncha buyurtmani tayyorlash "
                        "yoki yakunlash mumkin emas.",
                    )
            now = datetime.now(UTC)
            order.status = body.status
            if body.status == "accepted":
                order.accepted_at = now
                order.payment_status = "pending"
            elif body.status == "tayyor":
                order.ready_at = now
            order.updated_at = now
            self._changed(order, side, body.status, now)
            await self._event(session, "order.status_changed", order, account_id)
            if side == "provider" and body.status == "accepted":
                await append_order_notification(
                    session,
                    self._notification_repository,
                    order,
                    side="customer",
                    event="accepted",
                    title="Buyurtma qabul qilindi",
                    body="To'lovni amalga oshirib, chekni yuboring.",
                    action_type="make_payment",
                )
            elif side == "provider" and body.status == "tayyor":
                if self._taxi_service is not None:
                    await self._taxi_service.after_order_ready(session, order)
                await append_order_notification(
                    session,
                    self._notification_repository,
                    order,
                    side="customer",
                    event="ready",
                    title="Buyurtma tayyor bo'ldi",
                    body=(
                        "Do'kondan olib ketishingiz mumkin."
                        if order.order_type == "pickup"
                        else "Dostavka jarayoni boshlandi."
                    ),
                    action_type="view_ready",
                )
            elif side == "provider" and body.status in {"rejected", "cancelled"}:
                await append_order_notification(
                    session,
                    self._notification_repository,
                    order,
                    side="customer",
                    event=body.status,
                    title="Buyurtma bekor qilindi",
                    body=order.title,
                )
            elif side == "customer" and body.status == "cancelled":
                await append_order_notification(
                    session,
                    self._notification_repository,
                    order,
                    side="provider",
                    event="cancelled_by_customer",
                    title="Mijoz buyurtmani bekor qildi",
                    body=order.title,
                )
            await session.commit()
            return await self._project(session, order, side)

    async def handoff(
        self,
        *,
        order_id: int,
        account_id: int,
        account_type: AccountType,
        actor_staff_id: int | None = None,
    ) -> OrderRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            if side != "provider":
                raise ApiError(
                    403,
                    "order_provider_required",
                    "Bu amal faqat xizmat ko'rsatuvchiga tegishli.",
                )
            if order.order_type == "delivery":
                if order.status != "handoff_waiting_seller":
                    raise ApiError(
                        409,
                        "order_delivery_not_picked_up",
                        "Dostavkachi 'Dostavkani oldim' tugmasini hali bosmagan.",
                    )
                next_status = "in_delivery"
            else:
                if order.status != "tayyor":
                    raise ApiError(
                        409,
                        "order_handoff_invalid",
                        "Buyurtma hali topshirishga tayyor emas.",
                    )
                next_status = "pickup_waiting_customer"
            now = datetime.now(UTC)
            order.status = next_status
            order.handed_off_at = now
            order.seller_completed_at = now
            order.updated_at = now
            self._changed(order, side, "handoff", now)
            await self._event(session, "order.handed_off", order, account_id)
            await append_order_notification(
                session,
                self._notification_repository,
                order,
                side="customer",
                event="seller_handoff",
                title="Buyurtma topshirildi",
                body=(
                    "Buyurtma sizga yo'l oldi."
                    if order.order_type == "delivery"
                    else "Buyurtmani qabul qilganingizni tasdiqlang."
                ),
                action_type=""
                if order.order_type == "delivery"
                else "confirm_received",
            )
            if self._cash_register_service is not None:
                try:
                    await self._cash_register_service.post_order(
                        session,
                        order=order,
                        actor_staff_id=actor_staff_id,
                    )
                except Exception:
                    await session.rollback()
                    raise
            if order.order_type == "delivery" and self._taxi_service is not None:
                await self._taxi_service.after_order_handoff(session, order.id)
            await session.commit()
            return await self._project(session, order, side)

    async def received(
        self, *, order_id: int, account_id: int, account_type: AccountType
    ) -> OrderRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            if side != "customer" or order.status not in {
                "pickup_waiting_customer",
                "delivered_waiting_customer",
            }:
                raise ApiError(
                    409,
                    "order_received_invalid",
                    "Buyurtmani qabul qilish bosqichi hali kelmagan.",
                )
            now = datetime.now(UTC)
            order.status = "done"
            order.customer_received_at = now
            order.updated_at = now
            self._changed(order, side, "completed", now)
            await self._event(session, "order.completed", order, account_id)
            await append_order_notification(
                session,
                self._notification_repository,
                order,
                side="provider",
                event="customer_received",
                title="Buyurtma qabul qilindi",
                body="Buyurtmachi buyurtmani olganini tasdiqladi.",
            )
            if order.order_type == "delivery" and self._taxi_service is not None:
                await self._taxi_service.after_order_received(session, order.id)
            await session.commit()
            return await self._project(session, order, side)
