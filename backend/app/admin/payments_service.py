"""Admin to'lov navbati: ro'yxat, tafsilot, chek, narx va rekvizitlar.

Qaror qabul qilish `PaymentService.review` ga topshiriladi — obunani
yoqish mantiqi u yerda, ikki nusxa saqlanmaydi.

Javoblarda chek faylining yo'li chiqmaydi: faqat qisqa muddatli
imzolangan havola beriladi (v1656 da fayl to'g'ridan-to'g'ri uzatilardi).
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account
from app.admin.schemas import (
    AdminMethodRow,
    AdminMethodWrite,
    AdminPaymentAttempt,
    AdminPaymentDetail,
    AdminPaymentRow,
    AdminPriceRow,
    AdminPriceUpdate,
    AdminReceiptLink,
)
from app.core.errors import ApiError
from app.payments.model import (
    PaymentAttempt,
    PaymentMethod,
    PaymentRequest,
    PlatformPrice,
)


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]

STATUSES = ("pending", "approved", "rejected", "cancelled")
SERVICE_TYPES = ("subscription", "advertisement", "listing")
RECEIPT_URL_TTL_SECONDS = 300


def _row(request: PaymentRequest, login: str) -> dict[str, Any]:
    return {
        "id": request.id,
        "request_code": request.request_code,
        "actor_type": request.actor_type,
        "account_id": request.account_id,
        "account_login": login,
        "service_type": request.service_type,
        "plan_code": request.plan_code,
        "duration_months": request.duration_months,
        "quantity": request.quantity,
        "amount": request.amount_snapshot,
        "currency": request.currency,
        "price_code": request.price_code,
        "status": request.status,
        "public_reason": request.public_reason,
        "reviewed_by_admin_tg_id": request.reviewed_by_admin_tg_id,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
    }


class AdminPaymentService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        now: Callable[[], int],
        download_url_provider: Callable[..., str] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._now = now
        self._download_url = download_url_provider

    async def list_payments(
        self,
        *,
        status: str = "",
        service_type: str = "",
        limit: int = 100,
    ) -> list[AdminPaymentRow]:
        if status and status not in STATUSES:
            raise ApiError(
                400, "payment_status_invalid", "To‘lov holati noto‘g‘ri."
            )
        if service_type and service_type not in SERVICE_TYPES:
            raise ApiError(
                400, "payment_service_invalid", "Xizmat turi noto‘g‘ri."
            )
        statement = (
            select(PaymentRequest, Account.login)
            .join(Account, Account.id == PaymentRequest.account_id)
        )
        if status:
            statement = statement.where(PaymentRequest.status == status)
        if service_type:
            statement = statement.where(
                PaymentRequest.service_type == service_type
            )
        # Kutilayotganlar birinchi, keyin eng yangisi.
        statement = statement.order_by(
            PaymentRequest.created_at.desc(), PaymentRequest.id.desc()
        ).limit(max(1, min(500, limit)))
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).all()
            result = [
                AdminPaymentRow(**_row(request, login))
                for request, login in rows
            ]
            await session.rollback()
        return result

    async def detail(self, payment_id: int) -> AdminPaymentDetail:
        async with self._session_factory() as session:
            request, login, method_name = await self._require(
                session, payment_id
            )
            attempts = list((await session.scalars(
                select(PaymentAttempt)
                .where(PaymentAttempt.payment_request_id == request.id)
                .order_by(PaymentAttempt.attempt_no)
            )).all())
            result = AdminPaymentDetail(
                **_row(request, login),
                target_id=request.target_id,
                payment_method_id=request.payment_method_id,
                payment_method_name=method_name,
                internal_note=request.internal_note,
                approved_at=request.approved_at,
                rejected_at=request.rejected_at,
                cancelled_at=request.cancelled_at,
                attempts=[
                    AdminPaymentAttempt(
                        attempt_no=attempt.attempt_no,
                        review_status=attempt.review_status,
                        review_reason=attempt.review_reason,
                        submitted_at=attempt.submitted_at,
                        receipt_mime=attempt.receipt_mime,
                        receipt_sha256=attempt.receipt_sha256,
                        has_receipt=bool(attempt.receipt_object_key),
                    )
                    for attempt in attempts
                ],
            )
            await session.rollback()
        return result

    async def receipt_link(self, payment_id: int) -> AdminReceiptLink:
        """Oxirgi chek uchun qisqa muddatli imzolangan havola."""
        if self._download_url is None:
            raise ApiError(
                503,
                "receipt_storage_unavailable",
                "Chek saqlash xizmati sozlanmagan.",
            )
        async with self._session_factory() as session:
            await self._require(session, payment_id)
            attempt = await session.scalar(
                select(PaymentAttempt)
                .where(PaymentAttempt.payment_request_id == payment_id)
                .order_by(PaymentAttempt.attempt_no.desc())
                .limit(1)
            )
            if attempt is None or not attempt.receipt_object_key:
                raise ApiError(
                    404, "receipt_not_found", "Kvitansiya topilmadi."
                )
            object_key = attempt.receipt_object_key
            mime = attempt.receipt_mime
            await session.rollback()
        return AdminReceiptLink(
            url=self._download_url(
                object_key, expires_in=RECEIPT_URL_TTL_SECONDS
            ),
            mime=mime,
            expires_in=RECEIPT_URL_TTL_SECONDS,
        )

    # ------------------------------------------------------------- narxlar

    async def prices(self) -> list[AdminPriceRow]:
        async with self._session_factory() as session:
            rows = list((await session.scalars(
                select(PlatformPrice).order_by(
                    PlatformPrice.service_type, PlatformPrice.price_code
                )
            )).all())
            result = [
                AdminPriceRow(
                    id=price.id,
                    price_code=price.price_code,
                    service_type=price.service_type,
                    amount_uzs=price.amount_uzs,
                    config=price.config or {},
                    active=bool(price.active),
                    updated_at=price.updated_at,
                )
                for price in rows
            ]
            await session.rollback()
        return result

    async def update_price(
        self, *, price_id: int, body: AdminPriceUpdate
    ) -> AdminPriceRow:
        async with self._session_factory() as session:
            price = await session.scalar(
                select(PlatformPrice)
                .where(PlatformPrice.id == price_id)
                .with_for_update()
            )
            if price is None:
                raise ApiError(404, "price_not_found", "Tarif topilmadi.")
            price.amount_uzs = body.amount_uzs
            price.active = 1 if body.active else 0
            price.updated_at = self._now()
            result = AdminPriceRow(
                id=price.id,
                price_code=price.price_code,
                service_type=price.service_type,
                amount_uzs=price.amount_uzs,
                config=price.config or {},
                active=bool(price.active),
                updated_at=price.updated_at,
            )
            await session.commit()
        return result

    # --------------------------------------------------------- rekvizitlar

    async def methods(self) -> list[AdminMethodRow]:
        async with self._session_factory() as session:
            rows = list((await session.scalars(
                select(PaymentMethod).order_by(
                    PaymentMethod.sort_order, PaymentMethod.id
                )
            )).all())
            result = [self._method_row(method) for method in rows]
            await session.rollback()
        return result

    async def create_method(self, body: AdminMethodWrite) -> AdminMethodRow:
        now = self._now()
        async with self._session_factory() as session:
            method = PaymentMethod(
                method_type=body.method_type,
                name=body.name,
                details=body.details,
                recipient_name=body.recipient_name,
                instructions=body.instructions,
                sort_order=body.sort_order,
                active=1 if body.active else 0,
                created_at=now,
                updated_at=now,
            )
            session.add(method)
            await session.flush()
            result = self._method_row(method)
            await session.commit()
        return result

    async def update_method(
        self, *, method_id: int, body: AdminMethodWrite
    ) -> AdminMethodRow:
        async with self._session_factory() as session:
            method = await session.scalar(
                select(PaymentMethod)
                .where(PaymentMethod.id == method_id)
                .with_for_update()
            )
            if method is None:
                raise ApiError(
                    404, "payment_method_not_found", "To‘lov usuli topilmadi."
                )
            method.method_type = body.method_type
            method.name = body.name
            method.details = body.details
            method.recipient_name = body.recipient_name
            method.instructions = body.instructions
            method.sort_order = body.sort_order
            method.active = 1 if body.active else 0
            method.updated_at = self._now()
            result = self._method_row(method)
            await session.commit()
        return result

    # ------------------------------------------------------------ yordamchi

    @staticmethod
    def _method_row(method: PaymentMethod) -> AdminMethodRow:
        return AdminMethodRow(
            id=method.id,
            method_type=method.method_type,
            name=method.name,
            recipient_name=method.recipient_name,
            instructions=method.instructions,
            details=method.details or {},
            sort_order=method.sort_order,
            active=bool(method.active),
        )

    @staticmethod
    async def _require(
        session: AsyncSession, payment_id: int
    ) -> tuple[PaymentRequest, str, str]:
        row = (await session.execute(
            select(PaymentRequest, Account.login, PaymentMethod.name)
            .join(Account, Account.id == PaymentRequest.account_id)
            .join(
                PaymentMethod,
                PaymentMethod.id == PaymentRequest.payment_method_id,
                isouter=True,
            )
            .where(PaymentRequest.id == payment_id)
        )).first()
        if row is None:
            raise ApiError(404, "payment_not_found", "To‘lov topilmadi.")
        request, login, method_name = row
        return request, login, method_name or ""
