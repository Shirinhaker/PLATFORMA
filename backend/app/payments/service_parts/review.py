"""Ariza korigi va obunani faollashtirish."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.payments.model import (
    BusinessSubscription,
    PaymentAttempt,
    PaymentRequest,
)
from app.payments.schemas import (
    PaymentRequestRead,
)
from app.payments.service_parts.base import PaymentServiceBase
from app.payments.service_parts.helpers import (
    _add_months,
    _row,
)


class ReviewMixin(PaymentServiceBase):
    async def review(
        self,
        *,
        payment_id: int,
        admin_telegram_id: int,
        decision: str,
        reason: str = "",
        internal_note: str = "",
    ) -> PaymentRequestRead:
        """Tasdiqlash, rad etish yoki bekor qilish.

        Faqat admin routeridan chaqiriladi — biznes egasi o'z to'lovini
        tasdiqlay olmasligi kerak.
        """
        reason = reason.strip()
        if decision not in {"approved", "rejected", "cancelled"}:
            raise ApiError(400, "payment_decision_invalid", "Qaror turi noto‘g‘ri.")
        if decision in {"rejected", "cancelled"} and not reason:
            raise ApiError(
                400,
                "payment_reason_required",
                "Sabab kiritilishi shart.",
            )
        async with self._session_factory() as session:
            request = await session.scalar(
                select(PaymentRequest)
                .where(PaymentRequest.id == payment_id)
                .with_for_update()
            )
            if request is None:
                raise ApiError(404, "payment_not_found", "To'lov topilmadi.")
            if request.status != "pending":
                raise ApiError(
                    409,
                    "payment_already_reviewed",
                    "To'lov holati allaqachon o'zgargan.",
                )
            now = self._now()
            if decision == "approved":
                await self._activate(session, request, now)
            previous = request.status
            request.status = decision
            request.reviewed_by_admin_tg_id = admin_telegram_id
            request.public_reason = reason
            if internal_note:
                request.internal_note = internal_note[:1000]
            request.updated_at = now
            if decision == "approved":
                request.approved_at = now
            elif decision == "rejected":
                request.rejected_at = now
            else:
                request.cancelled_at = now
            await session.execute(
                PaymentAttempt.__table__.update()
                .where(
                    PaymentAttempt.payment_request_id == request.id,
                    PaymentAttempt.review_status == "pending",
                )
                .values(
                    review_status=(
                        "approved" if decision == "approved" else "rejected"
                    ),
                    reviewed_at=now,
                    review_reason=reason,
                )
            )
            self._add_event(
                session,
                request,
                from_status=previous,
                to_status=decision,
                actor_kind="admin",
                actor_id=str(admin_telegram_id),
                reason=reason,
                now=now,
            )
            await session.flush()
            response = _row(request, await self._attempts(session, request.id))
            await session.commit()
            return response

    async def _activate(
        self,
        session: AsyncSession,
        request: PaymentRequest,
        now: int,
    ) -> None:
        """Tasdiqlangan to'lovni xizmatga aylantiradi."""
        if self._activator is not None:
            await self._activator(session, request, now)
            return
        if request.service_type == "advertisement":
            if self._advertisements is None or request.target_id is None:
                raise ApiError(
                    409,
                    "advertisement_target_missing",
                    "To‘lov qaysi reklamaga tegishli ekani noma’lum.",
                )
            await self._advertisements.activate_paid(
                session,
                advertisement_id=request.target_id,
                account_id=request.account_id,
                now=now,
            )
            return
        if request.service_type == "listing":
            if self._listings is None or request.target_id is None:
                raise ApiError(
                    409,
                    "listing_target_missing",
                    "To‘lov qaysi e’longa tegishli ekani noma’lum.",
                )
            await self._listings.activate_paid(
                session,
                listing_id=request.target_id,
                account_id=request.account_id,
                now=now,
            )
            return
        if request.service_type != "subscription":
            return
        existing = await session.scalar(
            select(BusinessSubscription).where(
                BusinessSubscription.payment_request_id == request.id
            )
        )
        if existing is not None:
            # Idempotent: bir to'lov ikki marta obunaga aylanmaydi.
            return
        current = await session.scalar(
            select(BusinessSubscription)
            .where(
                BusinessSubscription.business_account_id == request.account_id,
                BusinessSubscription.status == "active",
            )
            .order_by(BusinessSubscription.expires_at.desc())
        )
        base = now
        if current is not None:
            if current.plan_code == request.plan_code:
                # v1656: bir xil tarif uzaytiriladi.
                base = max(now, current.expires_at)
            await session.execute(
                BusinessSubscription.__table__.update()
                .where(
                    BusinessSubscription.business_account_id == request.account_id,
                    BusinessSubscription.status == "active",
                )
                .values(status="superseded")
            )
        session.add(
            BusinessSubscription(
                business_account_id=request.account_id,
                legacy_source_id=None,
                plan_code=request.plan_code,
                duration_months=request.duration_months,
                starts_at=now,
                expires_at=_add_months(base, request.duration_months),
                status="active",
                is_demo=0,
                payment_request_id=request.id,
                created_at=now,
            )
        )
