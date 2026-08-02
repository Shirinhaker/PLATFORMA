from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, status

from app.accounts.model import AccountType
from app.auth.dependencies import CurrentAccount, require_csrf, require_current_account
from app.core.errors import ApiError
from app.queues.schemas import (
    QueueBusinessSetupRead,
    QueueCreate,
    QueueEntryRead,
    QueueOfflineCreate,
    QueueOptionsRead,
    QueueProviderRead,
    QueueProviderWrite,
    QueueSlotsRead,
    QueueStatusChange,
    QueueSwap,
)
from app.queues.service import QueueService


router = APIRouter(prefix="/api/v1/queues", tags=["queues"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
QueueId = Annotated[int, Path(gt=0)]
ProviderId = Annotated[int, Path(gt=0)]


def queue_service(request: Request) -> QueueService:
    return request.app.state.queue_service


def require_business(current: CurrentAccount) -> int:
    if current.account_type is not AccountType.BUSINESS:
        raise ApiError(
            403,
            "queue_business_required",
            "Bu bo‘lim faqat biznes kabinetida ishlaydi.",
        )
    return current.account_id


@router.get("/options", response_model=QueueOptionsRead)
async def queue_options(
    request: Request,
    business_public_id: Annotated[str, Query(min_length=1, max_length=64)],
    item_public_id: Annotated[str, Query(min_length=1, max_length=64)],
    queue_date: date | None = None,
):
    return await queue_service(request).options(
        business_public_id=business_public_id,
        item_public_id=item_public_id,
        queue_date=queue_date,
    )


@router.get("/slots", response_model=QueueSlotsRead)
async def queue_slots(
    request: Request,
    business_public_id: Annotated[str, Query(min_length=1, max_length=64)],
    item_public_id: Annotated[str, Query(min_length=1, max_length=64)],
    provider_id: Annotated[int, Query(gt=0)],
    queue_date: date | None = None,
):
    return await queue_service(request).slots(
        business_public_id=business_public_id,
        item_public_id=item_public_id,
        provider_id=provider_id,
        queue_date=queue_date,
    )


@router.get("/business/setup", response_model=QueueBusinessSetupRead)
async def business_queue_setup(request: Request, current: CurrentRead):
    return await queue_service(request).business_setup(
        business_account_id=require_business(current)
    )


@router.get("/business/providers", response_model=list[QueueProviderRead])
async def business_queue_providers(request: Request, current: CurrentRead):
    return await queue_service(request).list_providers(
        business_account_id=require_business(current)
    )


@router.post(
    "/business/providers",
    response_model=QueueProviderRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_business_queue_provider(
    body: QueueProviderWrite,
    request: Request,
    current: CurrentWrite,
):
    return await queue_service(request).create_provider(
        business_account_id=require_business(current),
        body=body,
    )


@router.put(
    "/business/providers/{provider_id}",
    response_model=QueueProviderRead,
)
async def update_business_queue_provider(
    provider_id: ProviderId,
    body: QueueProviderWrite,
    request: Request,
    current: CurrentWrite,
):
    return await queue_service(request).update_provider(
        business_account_id=require_business(current),
        provider_id=provider_id,
        body=body,
    )


@router.get("/business/entries", response_model=list[QueueEntryRead])
async def business_queue_entries(
    request: Request,
    current: CurrentRead,
    queue_date: date | None = None,
):
    return await queue_service(request).list_business(
        business_account_id=require_business(current),
        queue_date=queue_date,
    )


@router.post(
    "/business/entries",
    response_model=QueueEntryRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_business_offline_queue(
    body: QueueOfflineCreate,
    request: Request,
    current: CurrentWrite,
):
    return await queue_service(request).create_offline(
        business_account_id=require_business(current),
        body=body,
    )


@router.put(
    "/business/entries/{queue_id}/status",
    response_model=QueueEntryRead,
)
async def change_business_queue_status(
    queue_id: QueueId,
    body: QueueStatusChange,
    request: Request,
    current: CurrentWrite,
):
    return await queue_service(request).change_status(
        business_account_id=require_business(current),
        queue_id=queue_id,
        body=body,
    )


@router.post(
    "/business/entries/{queue_id}/swap",
    response_model=QueueEntryRead,
)
async def swap_business_queue(
    queue_id: QueueId,
    body: QueueSwap,
    request: Request,
    current: CurrentWrite,
):
    return await queue_service(request).swap(
        business_account_id=require_business(current),
        queue_id=queue_id,
        body=body,
    )


@router.post("", response_model=QueueEntryRead, status_code=status.HTTP_201_CREATED)
async def create_public_queue(
    body: QueueCreate,
    request: Request,
    current: CurrentWrite,
):
    return await queue_service(request).create_online(
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.get("/mine", response_model=list[QueueEntryRead])
async def my_queues(request: Request, current: CurrentRead):
    return await queue_service(request).list_mine(
        account_id=current.account_id,
        account_type=current.account_type,
    )


@router.post("/{queue_id}/cancel", response_model=QueueEntryRead)
async def cancel_my_queue(
    queue_id: QueueId,
    request: Request,
    current: CurrentWrite,
):
    return await queue_service(request).cancel_mine(
        account_id=current.account_id,
        account_type=current.account_type,
        queue_id=queue_id,
    )
