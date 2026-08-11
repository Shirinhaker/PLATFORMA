from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.account_settings.schemas import (
    BusinessCredentialsRead,
    BusinessCredentialsUpdate,
)
from app.account_settings.service import AccountSettingsService
from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
)
from app.core.errors import ApiError


router = APIRouter(prefix="/api/v1/account-settings", tags=["account-settings"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]


def account_settings_service(request: Request) -> AccountSettingsService:
    return request.app.state.account_settings_service


AccountSettingsServiceDep = Annotated[
    AccountSettingsService,
    Depends(account_settings_service),
]


def require_business_credentials_owner(current: CurrentAccount) -> None:
    if current.actor_type != "owner" or current.staff_id is not None:
        raise ApiError(
            403,
            "business_owner_required",
            "Bu amal faqat biznes egasi uchun.",
        )


@router.get(
    "/business-credentials",
    response_model=BusinessCredentialsRead,
)
async def get_business_credentials(
    current: CurrentRead,
    service: AccountSettingsServiceDep,
) -> BusinessCredentialsRead:
    require_business_credentials_owner(current)
    return await service.get_business_credentials(
        account_id=current.account_id,
        account_type=current.account_type,
    )


@router.put(
    "/business-credentials",
    response_model=BusinessCredentialsRead,
)
async def update_business_credentials(
    body: BusinessCredentialsUpdate,
    current: CurrentWrite,
    service: AccountSettingsServiceDep,
) -> BusinessCredentialsRead:
    require_business_credentials_owner(current)
    return await service.update_business_credentials(
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )
