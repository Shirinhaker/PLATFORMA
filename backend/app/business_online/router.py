from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.accounts.model import AccountType
from app.auth.dependencies import CurrentAccount, require_csrf, require_current_account
from app.business_online.schemas import (
    BusinessOnlineAction,
    BusinessOnlineCreate,
    BusinessOnlineMutationRead,
    BusinessOnlinePatch,
    BusinessOnlineResourceRead,
)
from app.business_online.service import BusinessOnlineService
from app.core.errors import ApiError


router = APIRouter(prefix="/api/v1/business-online", tags=["business-online"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]


def online_service(request: Request) -> BusinessOnlineService:
    return request.app.state.business_online_service


def require_business(current: CurrentAccount) -> None:
    if current.account_type is not AccountType.BUSINESS:
        raise ApiError(
            403,
            "business_online_forbidden",
            "Bu bo‘lim faqat biznes kabinetida ishlaydi.",
        )


@router.get("/{resource}", response_model=BusinessOnlineResourceRead)
async def read_resource(
    resource: str,
    current: CurrentRead,
    service: Annotated[BusinessOnlineService, Depends(online_service)],
) -> BusinessOnlineResourceRead:
    require_business(current)
    return BusinessOnlineResourceRead(
        resource=resource,
        items=await service.read_resource(current.account_id, resource),
    )


@router.post(
    "/{resource}",
    response_model=BusinessOnlineMutationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_record(
    resource: str,
    body: BusinessOnlineCreate,
    current: CurrentWrite,
    request: Request,
    service: Annotated[BusinessOnlineService, Depends(online_service)],
) -> BusinessOnlineMutationRead:
    require_business(current)
    item, items = await service.create_record(
        current.account_id,
        resource,
        body.record,
    )
    await request.app.state.profile_summary_service.invalidate(
        current.account_type,
        current.account_id,
    )
    return BusinessOnlineMutationRead(resource=resource, item=item, items=items)


@router.put(
    "/{resource}/{record_id}",
    response_model=BusinessOnlineMutationRead,
)
async def patch_record(
    resource: str,
    record_id: str,
    body: BusinessOnlinePatch,
    current: CurrentWrite,
    request: Request,
    service: Annotated[BusinessOnlineService, Depends(online_service)],
) -> BusinessOnlineMutationRead:
    require_business(current)
    item, items = await service.patch_record(
        current.account_id,
        resource,
        record_id,
        body.patch,
    )
    await request.app.state.profile_summary_service.invalidate(
        current.account_type,
        current.account_id,
    )
    return BusinessOnlineMutationRead(resource=resource, item=item, items=items)


@router.delete(
    "/{resource}/{record_id}",
    response_model=BusinessOnlineMutationRead,
)
async def delete_record(
    resource: str,
    record_id: str,
    current: CurrentWrite,
    request: Request,
    service: Annotated[BusinessOnlineService, Depends(online_service)],
) -> BusinessOnlineMutationRead:
    require_business(current)
    items = await service.delete_record(current.account_id, resource, record_id)
    await request.app.state.profile_summary_service.invalidate(
        current.account_type,
        current.account_id,
    )
    return BusinessOnlineMutationRead(resource=resource, items=items)


@router.post(
    "/{resource}/actions/{action}",
    response_model=BusinessOnlineMutationRead,
)
async def apply_action(
    resource: str,
    action: str,
    body: BusinessOnlineAction,
    current: CurrentWrite,
    request: Request,
    service: Annotated[BusinessOnlineService, Depends(online_service)],
) -> BusinessOnlineMutationRead:
    require_business(current)
    item, items = await service.apply_action(
        current.account_id,
        resource,
        action,
        record_id=body.record_id,
        data=body.payload,
    )
    await request.app.state.profile_summary_service.invalidate(
        current.account_type,
        current.account_id,
    )
    return BusinessOnlineMutationRead(resource=resource, item=item, items=items)


@router.options("/{path:path}", include_in_schema=False)
async def options_business_online(path: str) -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)
