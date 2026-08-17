from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.accounts.model import AccountType
from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
    require_staff_permission,
)
from app.business_online.schemas import (
    BusinessOnlineAction,
    BusinessOnlineCreate,
    BusinessOnlineMutationRead,
    BusinessOnlinePatch,
    BusinessOnlineResourceRead,
)
from app.business_online.service_parts import BusinessOnlineService
from app.core.errors import ApiError
from app.staff.permissions import RESOURCE_PERMISSIONS

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


def require_resource_permission(current: CurrentAccount, resource: str) -> None:
    required = RESOURCE_PERMISSIONS.get(resource, ("__business_owner__",))
    require_staff_permission(current, *required)


def _require_owned_item_image(
    current: CurrentAccount,
    resource: str,
    value: dict,
) -> None:
    if resource != "items":
        return
    object_key = str(value.get("image_object_key") or "").strip()
    if object_key and not object_key.startswith(
        f"private/business/{current.account_id}/catalog_item_image/"
    ):
        raise ApiError(
            403,
            "catalog_item_image_forbidden",
            "Mahsulot rasmi bu biznesga tegishli emas.",
        )


def _with_item_image_urls(
    request: Request,
    resource: str,
    items: list[dict],
) -> list[dict]:
    if resource != "items":
        return items
    result = []
    for item in items:
        enriched = dict(item)
        object_key = str(enriched.get("image_object_key") or "").strip()
        enriched["image_url"] = (
            request.app.state.r2.create_download_url(object_key) if object_key else ""
        )
        result.append(enriched)
    return result


@router.get("/{resource}", response_model=BusinessOnlineResourceRead)
async def read_resource(
    resource: str,
    current: CurrentRead,
    request: Request,
    service: Annotated[BusinessOnlineService, Depends(online_service)],
) -> BusinessOnlineResourceRead:
    require_business(current)
    require_resource_permission(current, resource)
    items = await service.read_resource(current.account_id, resource)
    return BusinessOnlineResourceRead(
        resource=resource,
        items=_with_item_image_urls(request, resource, items),
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
    require_resource_permission(current, resource)
    _require_owned_item_image(current, resource, body.record)
    item, items = await service.create_record(
        current.account_id,
        resource,
        body.record,
    )
    await request.app.state.profile_summary_service.invalidate(
        current.account_type,
        current.account_id,
    )
    displayed = _with_item_image_urls(request, resource, items)
    saved = next(
        (row for row in displayed if str(row.get("id")) == str(item.get("id"))),
        item,
    )
    return BusinessOnlineMutationRead(resource=resource, item=saved, items=displayed)


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
    require_resource_permission(current, resource)
    _require_owned_item_image(current, resource, body.patch)
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
    displayed = _with_item_image_urls(request, resource, items)
    saved = next(
        (row for row in displayed if str(row.get("id")) == str(item.get("id"))),
        item,
    )
    return BusinessOnlineMutationRead(resource=resource, item=saved, items=displayed)


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
    require_resource_permission(current, resource)
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
    # Reklama ekrani biznes va oddiy foydalanuvchida umumiy komponentdan
    # foydalanadi. `start_now` shu mavjud CSRF-himoyalangan action kanali
    # orqali relatsion reklama servisiga yo'naltiriladi.
    if resource == "advertisements" and action == "start_now":
        if current.account_type is AccountType.BUSINESS:
            require_resource_permission(current, resource)
        if body.record_id is None:
            raise ApiError(
                422,
                "advertisement_id_required",
                "Reklama tanlanmagan.",
            )
        try:
            advertisement_id = int(body.record_id)
        except (TypeError, ValueError):
            raise ApiError(
                404,
                "advertisement_not_found",
                "Reklama topilmadi.",
            ) from None
        advertisement_service = request.app.state.advertisement_authoring_service
        item = await advertisement_service.start_now(
            account_id=current.account_id,
            account_type=current.account_type,
            advertisement_id=advertisement_id,
        )
        items = await advertisement_service.list_mine(
            account_id=current.account_id,
            account_type=current.account_type,
        )
        return BusinessOnlineMutationRead(
            resource=resource,
            item=item.model_dump(),
            items=[row.model_dump() for row in items],
        )

    require_business(current)
    require_resource_permission(current, resource)
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
