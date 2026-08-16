"""To'lov: yuborish, tasdiqlash, qarzga yozish."""

from __future__ import annotations

from datetime import UTC, datetime

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.orders.model import OrderMessage
from app.orders.notifications import (
    append_order_notification,
)
from app.orders.schemas import (
    OrderPaymentDecision,
    OrderRead,
)
from app.orders.service_parts.base import OrderServiceBase


class PaymentMixin(OrderServiceBase):
    async def submit_payment(
        self, *, order_id: int, account_id: int, account_type: AccountType
    ) -> OrderRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            if side != "customer":
                raise ApiError(
                    403,
                    "order_customer_required",
                    "Bu amal faqat buyurtmachiga tegishli.",
                )
            if order.status != "accepted":
                raise ApiError(
                    409,
                    "order_not_accepted",
                    "Buyurtma sotuvchi tomonidan qabul qilinmagan.",
                )
            receipt = await self._repository.latest_receipt(
                session,
                order_id=order.id,
                sender_account_id=account_id,
            )
            if receipt is None:
                raise ApiError(
                    400,
                    "order_receipt_required",
                    "Avval to'lov cheki rasmini buyurtma chatiga yuboring.",
                )
            now = datetime.now(UTC)
            order.receipt_message_id = receipt.id
            order.payment_status = "submitted"
            order.updated_at = now
            self._changed(order, side, "payment_submitted", now)
            await self._event(session, "order.payment_submitted", order, account_id)
            await append_order_notification(
                session,
                self._notification_repository,
                order,
                side="provider",
                event="payment_submitted",
                title="To'lov qilindi",
                body="To'lov cheki yuborildi. To'lovni tekshirib tasdiqlang.",
                action_type="confirm_payment",
            )
            await session.commit()
            return await self._project(session, order, side)

    async def set_payment(
        self,
        *,
        order_id: int,
        account_id: int,
        account_type: AccountType,
        body: OrderPaymentDecision,
        actor_staff_id: int | None = None,
        permissions: tuple[str, ...] | None = None,
    ) -> OrderRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            if side != "provider":
                raise ApiError(
                    403,
                    "order_provider_required",
                    "Bu amal faqat xizmat ko'rsatuvchiga tegishli.",
                )
            if order.status in {"done", "cancelled", "rejected"}:
                raise ApiError(
                    409,
                    "order_payment_finished",
                    "Yakunlangan buyurtmada to'lovni o'zgartirib bo'lmaydi.",
                )
            debt_link = None
            if body.status == "debt":
                self._require_debt_payment_permission(permissions)
                already_debt = order.pay_type == "qarz" and order.debtor_id is not None
                if not already_debt and order.status != "accepted":
                    raise ApiError(
                        409,
                        "order_debt_status_invalid",
                        "Faqat qabul qilingan buyurtma qarzga yoziladi.",
                    )
                debtor_id = order.debtor_id if already_debt else body.debtor_id
                if self._debt_ledger_service is None or debtor_id is None:
                    raise ApiError(
                        400,
                        "debt_debtor_required",
                        "Qarz uchun qarzdorni tanlang.",
                    )
                debt_link = (
                    await self._debt_ledger_service.create_order_debt_in_session(
                        session,
                        business_account_id=order.provider_account_id,
                        order_id=order.id,
                        debtor_id=debtor_id,
                        amount=order.total_amount,
                        note=f"Tashqi buyurtma #{order.id}",
                        actor_staff_id=actor_staff_id,
                    )
                )
                if already_debt:
                    await session.commit()
                    return await self._project(session, order, side)
            elif order.payment_status not in {"submitted", "recheck", "disputed"}:
                message = (
                    "Buyurtmachi to'lov cheki va 'To'lov qildim' tasdig'ini yubormagan."
                    if body.status == "confirmed"
                    else "To'lovni hozir tekshirib bo'lmaydi."
                )
                raise ApiError(409, "order_payment_transition_invalid", message)
            now = datetime.now(UTC)
            if body.status == "debt":
                assert debt_link is not None
                debtor, _transaction = debt_link
                order.payment_status = "confirmed"
                order.pay_type = "qarz"
                order.debtor_id = debtor.id
                order.status = "preparing"
                order.problem_open = False
                order.problem_resolved_at = now
                topic = "order.debt_confirmed"
            elif body.status == "confirmed":
                order.payment_status = "confirmed"
                order.pay_type = "karta"
                order.debtor_id = None
                order.status = "preparing"
                order.problem_open = False
                order.problem_resolved_at = now
                topic = "order.payment_confirmed"
            else:
                order.payment_status = body.status
                topic = (
                    "order.payment_rejected"
                    if body.status == "rejected"
                    else "order.payment_pending"
                )
            order.updated_at = now
            self._changed(order, side, body.status, now)
            system_text = {
                "confirmed": "✅ To'lov tasdiqlandi. Rahmat!",
                "debt": "📒 Buyurtma qarzga rasmiylashtirildi.",
                "rejected": (
                    "❌ To'lov tasdiqlanmadi. Iltimos, to'lovni tekshiring "
                    "yoki qayta yuboring."
                ),
                "pending": "⏳ To'lov kutilmoqda.",
            }[body.status]
            session.add(
                OrderMessage(
                    legacy_source_id=None,
                    order_id=order.id,
                    sender_account_id=account_id,
                    sender_kind=account_type.value,
                    text=system_text,
                    media_type="text",
                    media_object_key="",
                    legacy_media_url="",
                    file_name="",
                    reply_to_id=None,
                    edited_at=None,
                    deleted_at=None,
                    is_deleted=False,
                    created_at=now,
                )
            )
            await session.flush()
            await self._event(session, topic, order, account_id)
            if body.status in {"confirmed", "debt"}:
                await append_order_notification(
                    session,
                    self._notification_repository,
                    order,
                    side="customer",
                    event=(
                        "debt_confirmed"
                        if body.status == "debt"
                        else "payment_confirmed"
                    ),
                    title=(
                        "Buyurtma qarzga rasmiylashtirildi"
                        if body.status == "debt"
                        else "To'lov tasdiqlandi"
                    ),
                    body="Buyurtma tayyorlanmoqda.",
                )
            await session.commit()
            return await self._project(session, order, side)

    @staticmethod
    def _require_debt_payment_permission(
        permissions: tuple[str, ...] | None,
    ) -> None:
        if permissions is not None and not {
            "payment_confirm",
            "payment_review",
            "kassa",
        }.intersection(permissions):
            raise ApiError(
                403,
                "staff_permission_required",
                "Bu bo‘limga vakolatingiz yo‘q.",
            )
