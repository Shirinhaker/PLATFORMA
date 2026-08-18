"""Tolov arizasi: yuborish, royxat, qayta yuborish."""

from __future__ import annotations

import secrets

from sqlalchemy import func, select

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.payments.model import (
    PaymentAttempt,
    PaymentMethod,
    PaymentRequest,
    PlatformPrice,
)
from app.payments.schemas import (
    PaymentRequestCreate,
    PaymentRequestRead,
    PaymentResubmit,
)
from app.payments.service_parts.base import PaymentServiceBase
from app.payments.service_parts.helpers import (
    _row,
)


class RequestsMixin(PaymentServiceBase):
    async def create(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: PaymentRequestCreate,
    ) -> PaymentRequestRead:
        if (
            body.service_type == "subscription"
            and account_type is not AccountType.BUSINESS
        ):
            raise ApiError(
                403,
                "business_account_required",
                "Biznes tarifini faqat biznes kabineti sotib oladi.",
            )
        async with self._session_factory() as session:
            price = await session.scalar(
                select(PlatformPrice).where(
                    PlatformPrice.price_code == body.price_code,
                    PlatformPrice.service_type == body.service_type,
                    PlatformPrice.active == 1,
                )
            )
            if price is None:
                raise ApiError(
                    400,
                    "payment_price_inactive",
                    "Tanlangan tarif hozir faol emas.",
                )
            config = price.config or {}
            # v1656: tarif parametrlari kod bilan mos kelishi shart.
            if body.service_type == "subscription" and (
                body.plan_code != str(config.get("plan_code") or "")
                or body.duration_months != int(config.get("duration_months") or 0)
            ):
                raise ApiError(
                    400,
                    "payment_price_mismatch",
                    "Tarif parametrlari mos emas.",
                )
            method = await session.scalar(
                select(PaymentMethod).where(
                    PaymentMethod.id == body.payment_method_id,
                    PaymentMethod.active == 1,
                )
            )
            if method is None:
                raise ApiError(
                    400,
                    "payment_method_inactive",
                    "To'lov usuli faol emas.",
                )

            target_id = body.target_id
            if body.service_type == "listing":
                if self._listings is None or not body.target_public_id:
                    raise ApiError(
                        400,
                        "listing_target_required",
                        "To‘lov qaysi e’longa tegishli ekani ko‘rsatilmagan.",
                    )
                target_id = await self._listings.resolve_owned(
                    session,
                    public_id=body.target_public_id,
                    account_id=account_id,
                )

            now = self._now()
            amount = price.amount_uzs * body.quantity
            request = PaymentRequest(
                legacy_source_id=None,
                request_code="PAY-" + secrets.token_hex(6).upper(),
                actor_type=account_type.value,
                account_id=account_id,
                service_type=body.service_type,
                target_id=target_id,
                plan_code=body.plan_code,
                duration_months=body.duration_months,
                quantity=body.quantity,
                unit_price_snapshot=price.amount_uzs,
                amount_snapshot=amount,
                currency="UZS",
                price_code=price.price_code,
                target_snapshot={},
                payment_method_id=method.id,
                status="pending",
                created_at=now,
                updated_at=now,
            )
            session.add(request)
            await session.flush()
            self._add_attempt(session, request, body.receipt, attempt_no=1, now=now)
            self._add_event(
                session,
                request,
                from_status="",
                to_status="pending",
                actor_kind=account_type.value,
                actor_id=str(account_id),
                now=now,
            )
            await session.flush()
            response = _row(request, await self._attempts(session, request.id))
            await session.commit()
            return response

    async def list_mine(
        self,
        *,
        account_id: int,
    ) -> list[PaymentRequestRead]:
        async with self._session_factory() as session:
            requests = list(
                (
                    await session.scalars(
                        select(PaymentRequest)
                        .where(PaymentRequest.account_id == account_id)
                        .order_by(
                            PaymentRequest.created_at.desc(), PaymentRequest.id.desc()
                        )
                        .limit(200)
                    )
                ).all()
            )
            attempts: dict[int, list[PaymentAttempt]] = {}
            if requests:
                rows = list(
                    (
                        await session.scalars(
                            select(PaymentAttempt)
                            .where(
                                PaymentAttempt.payment_request_id.in_(
                                    [request.id for request in requests]
                                )
                            )
                            .order_by(PaymentAttempt.attempt_no)
                        )
                    ).all()
                )
                for row in rows:
                    attempts.setdefault(row.payment_request_id, []).append(row)
            response = [
                _row(request, attempts.get(request.id, [])) for request in requests
            ]
            await session.rollback()
            return response

    async def resubmit(
        self,
        *,
        account_id: int,
        payment_id: int,
        body: PaymentResubmit,
    ) -> PaymentRequestRead:
        """Rad etilgan so'rovga yangi chek biriktiradi."""
        async with self._session_factory() as session:
            request = await self._owned(session, account_id, payment_id, lock=True)
            if request.status not in {"pending", "rejected"}:
                raise ApiError(
                    409,
                    "payment_not_resubmittable",
                    "Bu to'lovga yangi chek biriktirib bo'lmaydi.",
                )
            now = self._now()
            highest = await session.scalar(
                select(func.max(PaymentAttempt.attempt_no)).where(
                    PaymentAttempt.payment_request_id == request.id
                )
            )
            await session.execute(
                PaymentAttempt.__table__.update()
                .where(
                    PaymentAttempt.payment_request_id == request.id,
                    PaymentAttempt.review_status == "pending",
                )
                .values(review_status="superseded", reviewed_at=now)
            )
            self._add_attempt(
                session,
                request,
                body.receipt,
                attempt_no=int(highest or 0) + 1,
                now=now,
            )
            previous = request.status
            request.status = "pending"
            request.public_reason = ""
            request.updated_at = now
            self._add_event(
                session,
                request,
                from_status=previous,
                to_status="pending",
                actor_kind=request.actor_type,
                actor_id=str(account_id),
                now=now,
            )
            await session.flush()
            response = _row(request, await self._attempts(session, request.id))
            await session.commit()
            return response
