from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.accounts.model import AccountType
from app.auth.dependencies import CurrentAccount, require_csrf, require_current_account
from app.core.errors import ApiError
from app.expenses.schemas import (
    ExpenseCategoryCreate,
    ExpenseCategoryCreated,
    ExpenseCategoryList,
    ExpenseCreate,
    ExpenseCreated,
    ExpenseDayRead,
)
from app.expenses.service import ExpenseService


router = APIRouter(prefix="/api/v1/expenses", tags=["expenses"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]


def expense_service(request: Request) -> ExpenseService:
    return request.app.state.expense_service


ExpenseServiceDep = Annotated[ExpenseService, Depends(expense_service)]


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


@router.get("", response_model=ExpenseDayRead)
async def list_expenses(
    current: CurrentRead,
    service: ExpenseServiceDep,
    day: Annotated[date | None, Query()] = None,
) -> ExpenseDayRead:
    return await service.list_expenses(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        day=day,
    )


@router.post("", response_model=ExpenseCreated, status_code=status.HTTP_201_CREATED)
async def create_expense(
    body: ExpenseCreate,
    current: CurrentWrite,
    service: ExpenseServiceDep,
) -> ExpenseCreated:
    return await service.create_expense(
        business_account_id=_business_id(current),
        actor_staff_id=current.staff_id,
        actor_name=current.name,
        permissions=_permissions(current),
        body=body,
    )


@router.get("/categories", response_model=ExpenseCategoryList)
async def list_categories(
    current: CurrentRead,
    service: ExpenseServiceDep,
) -> ExpenseCategoryList:
    return await service.list_categories(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
    )


@router.post(
    "/categories",
    response_model=ExpenseCategoryCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    body: ExpenseCategoryCreate,
    current: CurrentWrite,
    service: ExpenseServiceDep,
) -> ExpenseCategoryCreated:
    return await service.create_category(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        body=body,
    )


@router.delete("/{expense_id}", status_code=204)
async def delete_expense(
    expense_id: int,
    current: CurrentWrite,
    service: ExpenseServiceDep,
) -> Response:
    await service.delete_expense(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        expense_id=expense_id,
    )
    return Response(status_code=204)
