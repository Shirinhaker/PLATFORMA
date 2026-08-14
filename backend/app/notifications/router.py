from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, status

from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
    require_staff_permission,
)
from app.core.errors import ApiError
from app.notifications.schemas import (
    ActionNotificationListRead,
    NotificationFilterRead,
    NotificationFilterWrite,
    NotificationListRead,
    NotificationMutationRead,
    NotificationPreferenceRead,
    NotificationPreferenceWrite,
    PushDeviceRead,
    PushDeviceRemove,
    PushDeviceWrite,
    PushStatusRead,
)
from app.notifications.service import NotificationService


router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
NotificationId = Annotated[int, Path(gt=0)]
FilterId = Annotated[int, Path(gt=0)]


def service(request: Request) -> NotificationService:
    return request.app.state.notification_service


def require_access(current: CurrentAccount) -> None:
    require_staff_permission(current, "notifications")


def require_device_owner(current: CurrentAccount) -> None:
    if current.actor_type == "staff":
        raise ApiError(
            403,
            "notification_device_owner_required",
            "Push qurilmasini faqat akkaunt egasi boshqaradi.",
        )


@router.get("", response_model=NotificationListRead)
async def notifications(
    request: Request,
    current: CurrentRead,
    before_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    require_access(current)
    return await service(request).list(
        account_id=current.account_id,
        account_type=current.account_type,
        staff_id=current.staff_id,
        permissions=current.permissions,
        before_id=before_id,
        limit=limit,
    )


@router.get("/actions", response_model=ActionNotificationListRead)
async def actionable_notifications(request: Request, current: CurrentRead):
    require_access(current)
    return await service(request).actions(
        account_id=current.account_id,
        account_type=current.account_type,
        staff_id=current.staff_id,
        permissions=current.permissions,
    )


@router.put("/{notification_id}/read", response_model=NotificationMutationRead)
async def mark_read(
    notification_id: NotificationId,
    request: Request,
    current: CurrentWrite,
):
    require_access(current)
    return await service(request).mark_read(
        notification_id=notification_id,
        account_id=current.account_id,
        account_type=current.account_type,
        staff_id=current.staff_id,
        permissions=current.permissions,
    )


@router.put("/read-all", response_model=NotificationMutationRead)
async def mark_all_read(request: Request, current: CurrentWrite):
    require_access(current)
    return await service(request).mark_all_read(
        account_id=current.account_id,
        account_type=current.account_type,
        staff_id=current.staff_id,
        permissions=current.permissions,
    )


@router.get("/preferences", response_model=NotificationPreferenceRead)
async def preference(request: Request, current: CurrentRead):
    require_access(current)
    return await service(request).preference(
        account_id=current.account_id,
        account_type=current.account_type,
    )


@router.put("/preferences", response_model=NotificationPreferenceRead)
async def save_preference(
    body: NotificationPreferenceWrite,
    request: Request,
    current: CurrentWrite,
):
    require_access(current)
    return await service(request).save_preference(
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.get("/filters", response_model=list[NotificationFilterRead])
async def filters(request: Request, current: CurrentRead):
    require_access(current)
    return await service(request).filters(
        account_id=current.account_id,
        account_type=current.account_type,
    )


@router.post(
    "/filters",
    response_model=NotificationFilterRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_filter(
    body: NotificationFilterWrite,
    request: Request,
    current: CurrentWrite,
):
    require_access(current)
    return await service(request).add_filter(
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.delete("/filters/{filter_id}", response_model=NotificationMutationRead)
async def remove_filter(
    filter_id: FilterId,
    request: Request,
    current: CurrentWrite,
):
    require_access(current)
    return await service(request).remove_filter(
        filter_id=filter_id,
        account_id=current.account_id,
        account_type=current.account_type,
    )


@router.post("/devices", response_model=PushDeviceRead)
async def register_device(
    body: PushDeviceWrite,
    request: Request,
    current: CurrentWrite,
):
    require_device_owner(current)
    return await service(request).register_device(
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.delete("/devices", response_model=NotificationMutationRead)
async def unregister_device(
    body: PushDeviceRemove,
    request: Request,
    current: CurrentWrite,
):
    require_device_owner(current)
    return await service(request).unregister_device(
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.get("/push-status", response_model=PushStatusRead)
async def push_status(request: Request, current: CurrentRead):
    require_device_owner(current)
    return await service(request).push_status(
        account_id=current.account_id,
        account_type=current.account_type,
    )
