"""To'lov so'rovi: yaratish, qayta yuborish va ko'rib chiqish.

Oqim v1656 (`payment_api.py`) bilan bir xil:

    tarif tanlanadi → chek yuklanadi → so'rov yaratiladi
    → admin tasdiqlaydi yoki rad etadi
    → tasdiqlansa xizmat yoqiladi

Farqi bitta: chek fayli R2'da saqlanadi. v1656da u serverning lokal
diskida turardi va bir nechta nusxa ishlaganda topilmasdi.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
import secrets
import time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.payments.model import (
    BusinessSubscription,
    PaymentAttempt,
    PaymentEvent,
    PaymentMethod,
    PaymentRequest,
    PlatformPrice,
)
from app.payments.schemas import (
    PaymentAttemptRead,
    PaymentCatalogRead,
    PaymentDecision,
    PaymentMethodRead,
    PaymentPriceRead,
    PaymentReceipt,
    PaymentRequestCreate,
    PaymentRequestRead,
    PaymentResubmit,
)


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
Activator = Callable[..., object]


def _row(request: PaymentRequest, attempts: list[PaymentAttempt]) -> PaymentRequestRead:
    return PaymentRequestRead(
        id=request.id,
        request_code=request.request_code,
        service_type=request.service_type,
        status=request.status,
        plan_code=request.plan_code,
        duration_months=request.duration_months,
        quantity=request.quantity,
        amount=request.amount_snapshot,
        currency=request.currency,
        price_code=request.price_code,
        public_reason=request.public_reason,
        created_at=request.created_at,
        updated_at=request.updated_at,
        attempts=[
            PaymentAttemptRead(
                attempt_no=attempt.attempt_no,
                review_status=attempt.review_status,
                review_reason=attempt.review_reason,
                submitted_at=attempt.submitted_at,
            )
            for attempt in attempts
        ],
    )


class PaymentService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        now: Callable[[], int] | None = None,
        activator: Activator | None = None,
        download_url_provider: Callable[..., str] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._now = now or (lambda: int(time.time()))
        self._activator = activator
        self._download_url = download_url_provider

    async def catalog(self) -> PaymentCatalogRead:
        async with self._session_factory() as session:
            prices = list((await session.scalars(
                select(PlatformPrice)
                .where(PlatformPrice.active == 1)
                .order_by(PlatformPrice.service_type, PlatformPrice.amount_uzs)
            )).all())
            methods = list((await session.scalars(
                select(PaymentMethod)
                .where(PaymentMethod.active == 1)
                .order_by(PaymentMethod.sort_order, PaymentMethod.id)
            )).all())
            response = PaymentCatalogRead(
                prices=[
                    PaymentPriceRead(
                        price_code=price.price_code,
                        service_type=price.service_type,
                        amount_uzs=price.amount_uzs,
                        plan_code=str((price.config or {}).get("plan_code") or ""),
                        duration_months=int(
                            (price.config or {}).get("duration_months") or 0
                        ),
                    )
                    for price in prices
                ],
                methods=[
                    PaymentMethodRead(
                        id=method.id,
                        method_type=method.method_type,
                        name=method.name,
                        recipient_name=method.recipient_name,
                        instructions=method.instructions,
                        details=method.details or {},
                    )
                    for method in methods
                ],
            )
            await session.rollback()
            return response

    async def create(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: PaymentRequestCreate,
    ) -> PaymentRequestRead:
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
            if body.service_type == "subscription":
                # v1656: tarif parametrlari kod bilan mos kelishi shart.
                if (
                    body.plan_code != str(config.get("plan_code") or "")
                    or body.duration_months
                    != int(config.get("duration_months") or 0)
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

            now = self._now()
            amount = price.amount_uzs * body.quantity
            request = PaymentRequest(
                legacy_source_id=None,
                request_code="PAY-" + secrets.token_hex(6).upper(),
                actor_type=account_type.value,
                account_id=account_id,
                service_type=body.service_type,
                target_id=body.target_id,
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
            requests = list((await session.scalars(
                select(PaymentRequest)
                .where(PaymentRequest.account_id == account_id)
                .order_by(PaymentRequest.created_at.desc(), PaymentRequest.id.desc())
                .limit(200)
            )).all())
            attempts: dict[int, list[PaymentAttempt]] = {}
            if requests:
                rows = list((await session.scalars(
                    select(PaymentAttempt)
                    .where(
                        PaymentAttempt.payment_request_id.in_(
                            [request.id for request in requests]
                        )
                    )
                    .order_by(PaymentAttempt.attempt_no)
                )).all())
                for row in rows:
                    attempts.setdefault(row.payment_request_id, []).append(row)
            response = [
                _row(request, attempts.get(request.id, []))
                for request in requests
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
            raise ApiError(
                400, "payment_decision_invalid", "Qaror turi noto‘g‘ri."
            )
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
        if request.service_type != "subscription":
            # Reklama va e'lon o'z domenlarida yoqiladi — hozircha
            # faqat to'lov holati yoziladi.
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
                    BusinessSubscription.business_account_id
                    == request.account_id,
                    BusinessSubscription.status == "active",
                )
                .values(status="superseded")
            )
        session.add(BusinessSubscription(
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
        ))

    async def _owned(
        self,
        session: AsyncSession,
        account_id: int,
        payment_id: int,
        *,
        lock: bool = False,
    ) -> PaymentRequest:
        statement = select(PaymentRequest).where(
            PaymentRequest.id == payment_id,
            PaymentRequest.account_id == account_id,
        )
        if lock:
            statement = statement.with_for_update()
        request = await session.scalar(statement)
        if request is None:
            raise ApiError(404, "payment_not_found", "To'lov topilmadi.")
        return request

    @staticmethod
    async def _attempts(
        session: AsyncSession,
        payment_id: int,
    ) -> list[PaymentAttempt]:
        return list((await session.scalars(
            select(PaymentAttempt)
            .where(PaymentAttempt.payment_request_id == payment_id)
            .order_by(PaymentAttempt.attempt_no)
        )).all())

    @staticmethod
    def _add_attempt(
        session: AsyncSession,
        request: PaymentRequest,
        receipt: PaymentReceipt,
        *,
        attempt_no: int,
        now: int,
    ) -> None:
        session.add(PaymentAttempt(
            payment_request_id=request.id,
            attempt_no=attempt_no,
            receipt_object_key=receipt.object_key,
            receipt_filename=receipt.filename,
            receipt_mime=receipt.mime,
            receipt_sha256=receipt.sha256,
            submitted_at=now,
            review_status="pending",
        ))

    @staticmethod
    def _add_event(
        session: AsyncSession,
        request: PaymentRequest,
        *,
        from_status: str,
        to_status: str,
        actor_kind: str,
        actor_id: str,
        now: int,
        reason: str = "",
    ) -> None:
        session.add(PaymentEvent(
            payment_request_id=request.id,
            from_status=from_status,
            to_status=to_status,
            actor_kind=actor_kind,
            actor_id=actor_id,
            reason=reason,
            event_metadata={},
            created_at=now,
        ))


def _add_months(stamp: int, months: int) -> int:
    """Kalendar oy qo'shadi — v1656 `_add_calendar_months` bilan bir xil."""
    from datetime import UTC, datetime

    moment = datetime.fromtimestamp(stamp, UTC)
    month = moment.month - 1 + max(0, months)
    year = moment.year + month // 12
    month = month % 12 + 1
    day = min(moment.day, _days_in_month(year, month))
    return int(moment.replace(year=year, month=month, day=day).timestamp())


def _days_in_month(year: int, month: int) -> int:
    from calendar import monthrange

    return monthrange(year, month)[1]
