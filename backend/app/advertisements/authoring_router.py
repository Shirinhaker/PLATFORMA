"""Reklama joylash endpointlari.

Public reklamalar `router.py` da — u yerda sessiya talab qilinmaydi.
Bu yerda esa reklama egasining o'z kabineti.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response, status

from app.advertisements.schemas import (
    AdvertisementCreate,
    AdvertisementQuote,
    AdvertisementQuoteRequest,
    AdvertisementRates,
    AdvertisementRead,
)
from app.advertisements.service import AdvertisementService
from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
)


router = APIRouter(prefix="/api/v1/advertisements", tags=["advertisements"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
AdvertisementId = Annotated[int, Path(gt=0)]


def authoring_service(request: Request) -> AdvertisementService:
    return request.app.state.advertisement_authoring_service


ServiceDep = Annotated[AdvertisementService, Depends(authoring_service)]


@router.get("/rates", response_model=AdvertisementRates)
async def advertisement_rates(
    current: CurrentRead,
    service: ServiceDep,
) -> AdvertisementRates:
    del current
    return await service.rates()


@router.post("/price", response_model=AdvertisementQuote)
async def advertisement_price(
    body: AdvertisementQuoteRequest,
    current: CurrentRead,
    service: ServiceDep,
) -> AdvertisementQuote:
    """Narxni oldindan ko'rsatadi — hech narsa saqlanmaydi."""
    del current
    return await service.quote(body)


@router.post(
    "",
    response_model=AdvertisementRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_advertisement(
    body: AdvertisementCreate,
    current: CurrentWrite,
    service: ServiceDep,
) -> AdvertisementRead:
    """Reklama `payment_pending` bilan yaratiladi va hali ko'rinmaydi."""
    return await service.create(
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )


@router.get("/my", response_model=list[AdvertisementRead])
async def my_advertisements(
    current: CurrentRead,
    service: ServiceDep,
) -> list[AdvertisementRead]:
    return await service.list_mine(
        account_id=current.account_id,
        account_type=current.account_type,
    )


@router.delete("/{advertisement_id}", status_code=204)
async def delete_advertisement(
    advertisement_id: AdvertisementId,
    current: CurrentWrite,
    service: ServiceDep,
) -> Response:
    await service.delete(
        account_id=current.account_id,
        account_type=current.account_type,
        advertisement_id=advertisement_id,
    )
    return Response(status_code=204)
