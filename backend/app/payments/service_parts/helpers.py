"""Tolov xizmati uchun konstantalar va mayda hisoblar."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from app.payments.model import (
    BusinessSubscription,
    PaymentAttempt,
    PaymentRequest,
)
from app.payments.schemas import (
    BusinessSubscriptionRead,
    PaymentAttemptRead,
    PaymentRequestRead,
)

"""To'lov so'rovi: yaratish, qayta yuborish va ko'rib chiqish.

Oqim v1656 (`payment_api.py`) bilan bir xil:

    tarif tanlanadi → chek yuklanadi → so'rov yaratiladi
    → admin tasdiqlaydi yoki rad etadi
    → tasdiqlansa xizmat yoqiladi

Farqi bitta: chek fayli R2'da saqlanadi. v1656da u serverning lokal
diskida turardi va bir nechta nusxa ishlaganda topilmasdi.
"""


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


def _subscription_row(row: BusinessSubscription) -> BusinessSubscriptionRead:
    return BusinessSubscriptionRead(
        id=row.id,
        plan_code=row.plan_code,
        duration_months=row.duration_months,
        starts_at=row.starts_at,
        expires_at=row.expires_at,
        status=row.status,
        is_demo=bool(row.is_demo),
        is_virtual=False,
        created_at=row.created_at,
    )


def _virtual_free_subscription() -> BusinessSubscriptionRead:
    return BusinessSubscriptionRead(
        id=None,
        plan_code="free",
        duration_months=0,
        starts_at=0,
        expires_at=0,
        status="active",
        is_demo=False,
        is_virtual=True,
        created_at=0,
    )


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
