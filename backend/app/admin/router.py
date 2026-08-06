"""Admin paneli endpointlari.

Har bir endpoint alohida `koprik_admin_session` cookie'sini tekshiradi —
oddiy foydalanuvchi sessiyasi bu yerga kirmaydi.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response

from app.admin.dependencies import CurrentAdmin, AdminServiceDep
from app.admin.payments_service import AdminPaymentService
from app.admin.schemas import (
    AdminAuthStart,
    AdminAuthStarted,
    AdminAuthVerify,
    AdminDecision,
    AdminIdentity,
    AdminMethodRow,
    AdminMethodWrite,
    AdminPaymentDetail,
    AdminPaymentRow,
    AdminPriceRow,
    AdminPriceUpdate,
    AdminReceiptLink,
)
from app.payments.schemas import PaymentRequestRead
from app.payments.service import PaymentService


router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
PaymentId = Annotated[int, Path(gt=0)]


def admin_payment_service(request: Request) -> AdminPaymentService:
    return request.app.state.admin_payment_service


def payment_service(request: Request) -> PaymentService:
    return request.app.state.payment_service


PaymentsDep = Annotated[AdminPaymentService, Depends(admin_payment_service)]
ReviewDep = Annotated[PaymentService, Depends(payment_service)]


# ------------------------------------------------------------------- kirish


@router.post("/auth/start", response_model=AdminAuthStarted)
async def admin_auth_start(
    body: AdminAuthStart,
    service: AdminServiceDep,
) -> AdminAuthStarted:
    """Ro'yxatdagi Telegram ID ga bir martalik kod yuboradi."""
    result = await service.start(telegram_user_id=body.telegram_user_id)
    return AdminAuthStarted(**result)


@router.post("/auth/verify", response_model=AdminIdentity)
async def admin_auth_verify(
    body: AdminAuthVerify,
    request: Request,
    response: Response,
    service: AdminServiceDep,
) -> AdminIdentity:
    token = await service.verify(
        challenge_id=body.challenge_id, code=body.code
    )
    settings = request.app.state.settings
    response.set_cookie(
        settings.admin_cookie_name,
        token,
        max_age=settings.admin_session_ttl_seconds,
        httponly=True,
        secure=settings.environment in {"staging", "production"},
        samesite="lax",
        path="/",
    )
    telegram_user_id = await service.resolve(token)
    return AdminIdentity(telegram_user_id=telegram_user_id or 0)


@router.get("/auth/me", response_model=AdminIdentity)
async def admin_auth_me(admin: CurrentAdmin) -> AdminIdentity:
    return AdminIdentity(telegram_user_id=admin)


@router.post("/auth/logout", status_code=204)
async def admin_auth_logout(
    request: Request,
    response: Response,
    service: AdminServiceDep,
) -> Response:
    settings = request.app.state.settings
    await service.logout(request.cookies.get(settings.admin_cookie_name, ""))
    response.delete_cookie(settings.admin_cookie_name, path="/")
    return Response(status_code=204)


# ----------------------------------------------------------------- to'lovlar


@router.get("/payments", response_model=list[AdminPaymentRow])
async def admin_payments(
    admin: CurrentAdmin,
    service: PaymentsDep,
    status: Annotated[str, Query(max_length=20)] = "",
    service_type: Annotated[str, Query(max_length=20)] = "",
) -> list[AdminPaymentRow]:
    del admin
    return await service.list_payments(
        status=status, service_type=service_type
    )


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


# ------------------------------------------------------- narx va rekvizitlar


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
