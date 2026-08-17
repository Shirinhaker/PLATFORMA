"""To'lov arizalari, tariflar va to'lov usullari."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.admin.dependencies import CurrentAdmin
from app.admin.router_parts.constants import (
    PaymentId,
    PaymentsDep,
    ReviewDep,
)
from app.admin.schemas import (
    AdminDecision,
    AdminMethodRow,
    AdminMethodWrite,
    AdminPaymentDetail,
    AdminPaymentRow,
    AdminPriceRow,
    AdminPriceUpdate,
    AdminReceiptLink,
)
from app.payments.schemas import PaymentRequestRead

router = APIRouter()


@router.get("/payments", response_model=list[AdminPaymentRow])
async def admin_payments(
    admin: CurrentAdmin,
    service: PaymentsDep,
    status: Annotated[str, Query(max_length=20)] = "",
    service_type: Annotated[str, Query(max_length=20)] = "",
) -> list[AdminPaymentRow]:
    del admin
    return await service.list_payments(status=status, service_type=service_type)


@router.get("/payments/{payment_id}", response_model=AdminPaymentDetail)
async def admin_payment_detail(
    payment_id: PaymentId,
    admin: CurrentAdmin,
    service: PaymentsDep,
) -> AdminPaymentDetail:
    del admin
    return await service.detail(payment_id)


@router.get("/payments/{payment_id}/receipt", response_model=AdminReceiptLink)
async def admin_payment_receipt(
    payment_id: PaymentId,
    admin: CurrentAdmin,
    service: PaymentsDep,
) -> AdminReceiptLink:
    """Chekni ko'rish uchun qisqa muddatli havola."""
    del admin
    return await service.receipt_link(payment_id)


@router.post("/payments/{payment_id}/approve", response_model=PaymentRequestRead)
async def admin_approve_payment(
    payment_id: PaymentId,
    body: AdminDecision,
    admin: CurrentAdmin,
    review: ReviewDep,
) -> PaymentRequestRead:
    return await review.review(
        payment_id=payment_id,
        admin_telegram_id=admin,
        decision="approved",
        reason=body.reason,
        internal_note=body.internal_note,
    )


@router.post("/payments/{payment_id}/reject", response_model=PaymentRequestRead)
async def admin_reject_payment(
    payment_id: PaymentId,
    body: AdminDecision,
    admin: CurrentAdmin,
    review: ReviewDep,
) -> PaymentRequestRead:
    return await review.review(
        payment_id=payment_id,
        admin_telegram_id=admin,
        decision="rejected",
        reason=body.reason,
        internal_note=body.internal_note,
    )


@router.post("/payments/{payment_id}/cancel", response_model=PaymentRequestRead)
async def admin_cancel_payment(
    payment_id: PaymentId,
    body: AdminDecision,
    admin: CurrentAdmin,
    review: ReviewDep,
) -> PaymentRequestRead:
    return await review.review(
        payment_id=payment_id,
        admin_telegram_id=admin,
        decision="cancelled",
        reason=body.reason,
        internal_note=body.internal_note,
    )


@router.get("/prices", response_model=list[AdminPriceRow])
async def admin_prices(
    admin: CurrentAdmin,
    service: PaymentsDep,
) -> list[AdminPriceRow]:
    del admin
    return await service.prices()


@router.put("/prices/{price_id}", response_model=AdminPriceRow)
async def admin_update_price(
    price_id: Annotated[int, Path(gt=0)],
    body: AdminPriceUpdate,
    admin: CurrentAdmin,
    service: PaymentsDep,
) -> AdminPriceRow:
    del admin
    return await service.update_price(price_id=price_id, body=body)


@router.get("/payment-methods", response_model=list[AdminMethodRow])
async def admin_payment_methods(
    admin: CurrentAdmin,
    service: PaymentsDep,
) -> list[AdminMethodRow]:
    del admin
    return await service.methods()


@router.post("/payment-methods", response_model=AdminMethodRow, status_code=201)
async def admin_create_payment_method(
    body: AdminMethodWrite,
    admin: CurrentAdmin,
    service: PaymentsDep,
) -> AdminMethodRow:
    del admin
    return await service.create_method(body)


@router.put("/payment-methods/{method_id}", response_model=AdminMethodRow)
async def admin_update_payment_method(
    method_id: Annotated[int, Path(gt=0)],
    body: AdminMethodWrite,
    admin: CurrentAdmin,
    service: PaymentsDep,
) -> AdminMethodRow:
    del admin
    return await service.update_method(method_id=method_id, body=body)
