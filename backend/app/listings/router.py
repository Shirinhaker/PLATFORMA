from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response

from app.accounts.model import AccountType
from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
    require_staff_permission,
)
from app.core.errors import ApiError
from app.listings.schemas import ListingCreate, ListingPatch, ListingRead, ListingSaveRead
from app.listings.service import ListingService
from app.public_discovery.router import optional_current_account


router = APIRouter(prefix="/api/v1", tags=["listings"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
ListingPublicId = Annotated[str, Path(pattern=r"^l_[0-9a-f]{16}$")]


def service(request: Request) -> ListingService:
    return request.app.state.listing_service


def require_enabled(request: Request) -> None:
    if not request.app.state.settings.listings_enabled:
        raise ApiError(404, "feature_not_available", "E’lonlar hozircha ochilmagan.")


@router.get("/public/listings/counts", response_model=dict[str, int])
async def listing_counts(request: Request):
    require_enabled(request)
    return await service(request).counts()


@router.get("/public/listings", response_model=list[ListingRead])
async def list_public_listings(
    request: Request,
    cat: str = Query(default="", max_length=40),
    q: str = Query(default="", max_length=120),
    current: CurrentAccount | None = Depends(optional_current_account),
):
    require_enabled(request)
    return await service(request).list_public(
        category=cat.strip(),
        query=q.strip(),
        current_account_id=(
            current.account_id if current is not None else None
        ),
        current_account_type=current.account_type if current is not None else None,
    )


@router.get("/public/listings/{public_id}", response_model=ListingRead)
async def get_public_listing(
    request: Request,
    public_id: ListingPublicId,
    current: CurrentAccount | None = Depends(optional_current_account),
):
    require_enabled(request)
    listing = await service(request).get_public(
        public_id,
        current_account_id=(
            current.account_id if current is not None else None
        ),
        current_account_type=current.account_type if current is not None else None,
    )
    if listing is None:
        raise ApiError(404, "listing_not_found", "E'lon topilmadi.")
    return listing


@router.get("/listings/mine", response_model=list[ListingRead])
async def my_listings(request: Request, current: CurrentRead):
    require_enabled(request)
    require_staff_permission(current, "ads")
    return await service(request).list_owner(
        account_id=current.account_id,
        account_type=current.account_type,
    )


@router.post("/listings", response_model=ListingRead, status_code=201)
async def create_listing(body: ListingCreate, request: Request, current: CurrentWrite):
    require_enabled(request)
    require_staff_permission(current, "ads")
    return await service(request).create(
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.put("/listings/{public_id}", response_model=ListingRead)
async def patch_listing(
    public_id: ListingPublicId,
    body: ListingPatch,
    request: Request,
    current: CurrentWrite,
):
    require_enabled(request)
    require_staff_permission(current, "ads")
    return await service(request).patch(
        public_id=public_id,
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.delete("/listings/{public_id}", status_code=204)
async def delete_listing(
    public_id: ListingPublicId,
    request: Request,
    current: CurrentWrite,
):
    require_enabled(request)
    require_staff_permission(current, "ads")
    await service(request).delete(
        public_id=public_id,
        account_id=current.account_id,
        account_type=current.account_type,
    )
    return Response(status_code=204)


@router.post("/listings/{public_id}/save", response_model=ListingSaveRead)
async def toggle_listing_save(
    public_id: ListingPublicId,
    request: Request,
    current: CurrentWrite,
):
    require_enabled(request)
    require_staff_permission(current, "__business_owner__")
    return ListingSaveRead(saved=await service(request).toggle_save(
        public_id=public_id,
        account_id=current.account_id,
        account_type=current.account_type,
    ))


@router.get("/listings/saved", response_model=list[ListingRead])
async def saved_listings(request: Request, current: CurrentRead):
    require_enabled(request)
    require_staff_permission(current, "__business_owner__")
    if current.account_type is not AccountType.USER:
        return []
    return await service(request).list_saved(account_id=current.account_id)
