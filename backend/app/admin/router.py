"""Admin paneli endpointlari.

Har bir endpoint alohida `koprik_admin_session` cookie'sini tekshiradi —
oddiy foydalanuvchi sessiyasi bu yerga kirmaydi.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response

from app.admin.audit import request_meta
from app.admin.dependencies import CurrentAdmin, AdminServiceDep
from app.admin.moderation_service import AdminModerationService
from app.admin.payments_service import AdminPaymentService
from app.admin.reports_service import AdminReportsService
from app.admin.schemas import (
    AdminAccountDetail,
    AdminAccountRow,
    AdminAuthStart,
    AdminAuthStarted,
    AdminAuthVerify,
    AdminContentResult,
    AdminContentStatus,
    AdminContentWrite,
    AdminDecision,
    AdminIdentity,
    AdminMethodRow,
    AdminMethodWrite,
    AdminNoteRow,
    AdminNoteWrite,
    AdminPaymentDetail,
    AdminPaymentRow,
    AdminPriceRow,
    AdminPriceUpdate,
    AdminReceiptLink,
    AdminRestrictionResult,
    AdminRestrictionWrite,
    AuditDetail,
    AuditRow,
    ReportDecision,
    ReportRow,
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


# ------------------------------------------------------------- moderatsiya


def moderation_service(request: Request) -> AdminModerationService:
    return request.app.state.admin_moderation_service


def reports_service(request: Request) -> AdminReportsService:
    return request.app.state.admin_reports_service


ModerationDep = Annotated[AdminModerationService, Depends(moderation_service)]
ReportsDep = Annotated[AdminReportsService, Depends(reports_service)]
ActorType = Annotated[str, Path(pattern="^(user|business)$")]
ContentKind = Annotated[str, Path(min_length=1, max_length=32)]
AccountId = Annotated[int, Path(gt=0)]
ReportId = Annotated[int, Path(gt=0)]


def _meta(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return request_meta(
        request, settings.admin_audit_ip_secret or settings.csrf_secret
    )


@router.get("/accounts/{actor_type}", response_model=list[AdminAccountRow])
async def admin_accounts(
    actor_type: ActorType,
    admin: CurrentAdmin,
    service: ModerationDep,
    query: Annotated[str, Query(max_length=120)] = "",
    restriction: Annotated[str, Query(max_length=32)] = "",
) -> list[AdminAccountRow]:
    del admin
    rows = await service.list_accounts(
        actor_type=actor_type, query=query, restriction=restriction
    )
    return [AdminAccountRow(**row) for row in rows]


@router.get(
    "/accounts/{actor_type}/{account_id}", response_model=AdminAccountDetail
)
async def admin_account_detail(
    actor_type: ActorType,
    account_id: AccountId,
    admin: CurrentAdmin,
    service: ModerationDep,
) -> AdminAccountDetail:
    del admin
    return AdminAccountDetail(**await service.account_detail(
        actor_type=actor_type, account_id=account_id
    ))


@router.post(
    "/accounts/{actor_type}/{account_id}/restrict",
    response_model=AdminRestrictionResult,
)
async def admin_restrict_account(
    actor_type: ActorType,
    account_id: AccountId,
    body: AdminRestrictionWrite,
    request: Request,
    admin: CurrentAdmin,
    service: ModerationDep,
) -> AdminRestrictionResult:
    return AdminRestrictionResult(**await service.restrict(
        actor_type=actor_type,
        account_id=account_id,
        restriction=body.restriction,
        reason=body.reason,
        admin_tg_id=admin,
        meta=_meta(request),
    ))


@router.post(
    "/accounts/{actor_type}/{account_id}/unrestrict",
    response_model=AdminRestrictionResult,
)
async def admin_unrestrict_account(
    actor_type: ActorType,
    account_id: AccountId,
    body: AdminRestrictionWrite,
    request: Request,
    admin: CurrentAdmin,
    service: ModerationDep,
) -> AdminRestrictionResult:
    return AdminRestrictionResult(**await service.unrestrict(
        actor_type=actor_type,
        account_id=account_id,
        restriction=body.restriction,
        reason=body.reason,
        admin_tg_id=admin,
        meta=_meta(request),
    ))


@router.post(
    "/accounts/{actor_type}/{account_id}/notes",
    response_model=AdminNoteRow,
    status_code=201,
)
async def admin_add_note(
    actor_type: ActorType,
    account_id: AccountId,
    body: AdminNoteWrite,
    request: Request,
    admin: CurrentAdmin,
    service: ModerationDep,
) -> AdminNoteRow:
    return AdminNoteRow(**await service.add_note(
        actor_type=actor_type,
        account_id=account_id,
        note=body.note,
        admin_tg_id=admin,
        meta=_meta(request),
    ))


# ----------------------------------------------------------------- kontent


@router.get(
    "/content/{content_kind}/{content_id}", response_model=AdminContentStatus
)
async def admin_content_status(
    content_kind: ContentKind,
    content_id: AccountId,
    admin: CurrentAdmin,
    service: ModerationDep,
) -> AdminContentStatus:
    del admin
    return AdminContentStatus(**await service.content_status(
        content_kind=content_kind, content_id=content_id
    ))


# v1656: yashirish, tiklash va o'chirish uchta alohida yo'l edi.
CONTENT_ACTIONS = {"hide": "hidden", "restore": "visible", "remove": "removed"}


@router.post(
    "/content/{content_kind}/{content_id}/{action}",
    response_model=AdminContentResult,
)
async def admin_set_content_status(
    content_kind: ContentKind,
    content_id: AccountId,
    action: Annotated[str, Path(pattern="^(hide|restore|remove)$")],
    body: AdminContentWrite,
    request: Request,
    admin: CurrentAdmin,
    service: ModerationDep,
) -> AdminContentResult:
    return AdminContentResult(**await service.set_content_status(
        content_kind=content_kind,
        content_id=content_id,
        status=CONTENT_ACTIONS[action],
        reason=body.reason,
        admin_tg_id=admin,
        meta=_meta(request),
    ))


# -------------------------------------------------------------- shikoyatlar


@router.get("/reports", response_model=list[ReportRow])
async def admin_reports(
    admin: CurrentAdmin,
    service: ReportsDep,
    status: Annotated[str, Query(max_length=20)] = "",
) -> list[ReportRow]:
    del admin
    rows = await service.list_reports(status=status)
    return [ReportRow(**row) for row in rows]


@router.get("/reports/{report_id}", response_model=ReportRow)
async def admin_report_detail(
    report_id: ReportId,
    admin: CurrentAdmin,
    service: ReportsDep,
) -> ReportRow:
    del admin
    return ReportRow(**await service.report_detail(report_id))


@router.post("/reports/{report_id}/assign", response_model=ReportRow)
async def admin_assign_report(
    report_id: ReportId,
    request: Request,
    admin: CurrentAdmin,
    service: ReportsDep,
) -> ReportRow:
    return ReportRow(**await service.assign(
        report_id=report_id, admin_tg_id=admin, meta=_meta(request)
    ))


@router.post("/reports/{report_id}/resolve", response_model=ReportRow)
async def admin_resolve_report(
    report_id: ReportId,
    body: ReportDecision,
    request: Request,
    admin: CurrentAdmin,
    service: ReportsDep,
) -> ReportRow:
    return ReportRow(**await service.decide(
        report_id=report_id,
        decision="resolved",
        resolution=body.resolution,
        admin_tg_id=admin,
        meta=_meta(request),
    ))


@router.post("/reports/{report_id}/dismiss", response_model=ReportRow)
async def admin_dismiss_report(
    report_id: ReportId,
    body: ReportDecision,
    request: Request,
    admin: CurrentAdmin,
    service: ReportsDep,
) -> ReportRow:
    return ReportRow(**await service.decide(
        report_id=report_id,
        decision="dismissed",
        resolution=body.resolution,
        admin_tg_id=admin,
        meta=_meta(request),
    ))


# ------------------------------------------------------------------- audit


@router.get("/audit", response_model=list[AuditRow])
async def admin_audit(
    admin: CurrentAdmin,
    service: ReportsDep,
    action: Annotated[str, Query(max_length=80)] = "",
) -> list[AuditRow]:
    del admin
    rows = await service.list_audit(action=action)
    return [AuditRow(**row) for row in rows]


# Bu yo'l `/audit/{audit_id}` dan oldin turishi shart, aks holda
# "export.csv" son sifatida o'qilmoqchi bo'ladi.
@router.get("/audit/export.csv")
async def admin_audit_export(
    admin: CurrentAdmin,
    service: ReportsDep,
    action: Annotated[str, Query(max_length=80)] = "",
) -> Response:
    del admin
    return Response(
        content=await service.audit_csv(action=action),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="admin-audit.csv"',
            "Cache-Control": "no-store, private",
        },
    )


@router.get("/audit/{audit_id}", response_model=AuditDetail)
async def admin_audit_detail(
    audit_id: ReportId,
    admin: CurrentAdmin,
    service: ReportsDep,
) -> AuditDetail:
    del admin
    return AuditDetail(**await service.audit_detail(audit_id))
