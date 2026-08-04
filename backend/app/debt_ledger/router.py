from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, status

from app.accounts.model import AccountType
from app.auth.dependencies import CurrentAccount, require_csrf, require_current_account
from app.core.errors import ApiError
from app.debt_ledger.schemas import (
    DebtMutationRead,
    DebtTransactionCreate,
    DebtorCreate,
    DebtorCreated,
    DebtorDetailRead,
    DebtorRead,
)
from app.debt_ledger.service import DebtLedgerService


router = APIRouter(prefix="/api/v1/debt-ledger", tags=["debt-ledger"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
DebtorId = Annotated[int, Path(gt=0)]


def debt_service(request: Request) -> DebtLedgerService:
    return request.app.state.debt_ledger_service


DebtServiceDep = Annotated[DebtLedgerService, Depends(debt_service)]


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


@router.get("/debtors", response_model=list[DebtorRead])
async def list_debtors(current: CurrentRead, service: DebtServiceDep):
    return await service.list_debtors(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
    )


@router.post(
    "/debtors",
    response_model=DebtorCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_debtor(
    body: DebtorCreate,
    current: CurrentWrite,
    service: DebtServiceDep,
):
    return await service.create_debtor(
        business_account_id=_business_id(current),
        actor_staff_id=current.staff_id,
        permissions=_permissions(current),
        body=body,
    )


@router.get("/debtors/{debtor_id}", response_model=DebtorDetailRead)
async def get_debtor(
    debtor_id: DebtorId,
    current: CurrentRead,
    service: DebtServiceDep,
):
    return await service.get_debtor(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        debtor_id=debtor_id,
    )


@router.post(
    "/debtors/{debtor_id}/transactions",
    response_model=DebtMutationRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_transaction(
    debtor_id: DebtorId,
    body: DebtTransactionCreate,
    current: CurrentWrite,
    service: DebtServiceDep,
):
    return await service.add_transaction(
        business_account_id=_business_id(current),
        actor_staff_id=current.staff_id,
        actor_name=current.name,
        permissions=_permissions(current),
        debtor_id=debtor_id,
        body=body,
    )
