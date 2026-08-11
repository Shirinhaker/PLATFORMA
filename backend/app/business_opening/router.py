from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.accounts.model import AccountType
from app.auth.dependencies import CurrentAccount, require_csrf
from app.business_opening.schemas import BusinessOpeningRead, BusinessOpeningWrite
from app.business_opening.service import BusinessOpeningService
from app.core.errors import ApiError


router = APIRouter(prefix="/api/v1/business-opening", tags=["business-opening"])
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]


def business_opening_service(request: Request) -> BusinessOpeningService:
    return request.app.state.business_opening_service


BusinessOpeningServiceDep = Annotated[
    BusinessOpeningService,
    Depends(business_opening_service),
]


def require_business_opening_owner(current: CurrentAccount) -> None:
    if (
        current.account_type is not AccountType.USER
        or current.actor_type != "owner"
        or current.staff_id is not None
    ):
        raise ApiError(
            403,
            "business_opening_owner_required",
            "Biznesni faqat foydalanuvchi kabineti egasi ochishi mumkin.",
        )


@router.post("", response_model=BusinessOpeningRead)
async def open_business(
    body: BusinessOpeningWrite,
    current: CurrentWrite,
    service: BusinessOpeningServiceDep,
) -> BusinessOpeningRead:
    require_business_opening_owner(current)
    return await service.open_business(
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )
