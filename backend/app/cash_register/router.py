from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.accounts.model import AccountType
from app.auth.dependencies import CurrentAccount, require_csrf, require_current_account
from app.cash_register.schemas import (
    CashCatalogItemRead,
    CashPaymentUpdate,
    CashReceiptCreate,
    CashReceiptCreated,
    CashReceiptRead,
    CashRegisterRead,
)
from app.cash_register.service import CashRegisterService
from app.core.errors import ApiError


router = APIRouter(prefix="/api/v1/cash-register", tags=["cash-register"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]


def cash_service(request: Request) -> CashRegisterService:
    return request.app.state.cash_register_service


CashServiceDep = Annotated[CashRegisterService, Depends(cash_service)]


def _business_id(current: CurrentAccount) -> int:
    if current.account_type is not AccountType.BUSINESS:
        raise ApiError(
            403,
            "business_account_required",
            "Bu bo‘lim faqat biznes akkaunt uchun.",
        )
    return current.account_id


def _permissions(current: CurrentAccount) -> tuple[str, ...] | None:
    return current.permissions if current.actor_type == "staff" else None


@router.get("", response_model=CashRegisterRead)
async def get_cash_register(
    current: CurrentRead,
    service: CashServiceDep,
    day: Annotated[date | None, Query()] = None,
) -> CashRegisterRead:
    return await service.list_receipts(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        day=day,
    )


@router.get("/catalog", response_model=list[CashCatalogItemRead])
async def get_cash_catalog(
    current: CurrentRead,
    service: CashServiceDep,
) -> list[CashCatalogItemRead]:
    return await service.catalog(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
    )


@router.post(
    "/receipts",
    response_model=CashReceiptCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_cash_receipt(
    body: CashReceiptCreate,
    current: CurrentWrite,
    service: CashServiceDep,
) -> CashReceiptCreated:
    return await service.create_receipt(
        business_account_id=_business_id(current),
        actor_staff_id=current.staff_id,
        actor_name="",
        permissions=_permissions(current),
        body=body,
    )


@router.put("/receipts/{receipt_id}/payment", response_model=CashReceiptRead)
async def update_cash_order_payment(
    receipt_id: int,
    body: CashPaymentUpdate,
    current: CurrentWrite,
    service: CashServiceDep,
) -> CashReceiptRead:
    return await service.update_order_payment(
        business_account_id=_business_id(current),
        actor_staff_id=current.staff_id,
        permissions=_permissions(current),
        receipt_id=receipt_id,
        body=body,
    )


@router.delete("/receipts/{receipt_id}", status_code=204)
async def delete_cash_receipt(
    receipt_id: int,
    current: CurrentWrite,
    service: CashServiceDep,
) -> Response:
    await service.delete_receipt(
        business_account_id=_business_id(current),
        actor_staff_id=current.staff_id,
        permissions=_permissions(current),
        receipt_id=receipt_id,
    )
    return Response(status_code=204)
