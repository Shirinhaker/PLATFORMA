from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, status

from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
)
from app.payments.schemas import (
    PaymentCatalogRead,
    PaymentRequestCreate,
    PaymentRequestRead,
    PaymentResubmit,
)
from app.payments.service import PaymentService


router = APIRouter(prefix="/api/v1/payments", tags=["payments"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
PaymentId = Annotated[int, Path(gt=0)]


def payment_service(request: Request) -> PaymentService:
    return request.app.state.payment_service


ServiceDep = Annotated[PaymentService, Depends(payment_service)]


@router.get("/catalog", response_model=PaymentCatalogRead)
async def payment_catalog(
    current: CurrentRead,
    service: ServiceDep,
) -> PaymentCatalogRead:
    """Tariflar va to'lov usullari."""
    del current
    return await service.catalog()


@router.post(
    "/requests",
    response_model=PaymentRequestRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_request(
    body: PaymentRequestCreate,
    current: CurrentWrite,
    service: ServiceDep,
) -> PaymentRequestRead:
    return await service.create(
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.get("/my", response_model=list[PaymentRequestRead])
async def my_payments(
    current: CurrentRead,
    service: ServiceDep,
) -> list[PaymentRequestRead]:
    return await service.list_mine(account_id=current.account_id)


@router.post("/{payment_id}/resubmit", response_model=PaymentRequestRead)
async def resubmit_payment(
    payment_id: PaymentId,
    body: PaymentResubmit,
    current: CurrentWrite,
    service: ServiceDep,
) -> PaymentRequestRead:
    return await service.resubmit(
        account_id=current.account_id,
        payment_id=payment_id,
        body=body,
    )


# Tasdiqlash va rad etish bu yerda emas — `/api/v1/admin/payments/...`
# ostida, alohida admin sessiyasi bilan. Ilgari ular shu routerda
# `require_business_owner` bilan turgan edi, ya'ni har qanday biznes
# egasi o'zining to'lovini o'zi tasdiqlay olardi.
