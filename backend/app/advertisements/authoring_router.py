"""Reklama joylash endpointlari.

Public reklamalar `router.py` da — u yerda sessiya talab qilinmaydi.
Bu yerda esa reklama egasining o'z kabineti.
"""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response, status

from app.advertisements.authoring_schemas import (
    AdvertisementCreate,
    AdvertisementQuote,
    AdvertisementQuoteRequest,
    AdvertisementRates,
    AdvertisementRead,
)
from app.advertisements.service import AdvertisementAuthoringService
from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
)
from app.core.errors import ApiError
from app.media.storage import UploadRejected


router = APIRouter(prefix="/api/v1/advertisements", tags=["advertisements"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
AdvertisementId = Annotated[int, Path(gt=0)]


def authoring_service(request: Request) -> AdvertisementAuthoringService:
    return request.app.state.advertisement_authoring_service


ServiceDep = Annotated[AdvertisementAuthoringService, Depends(authoring_service)]


async def verify_advertisement_image(
    request: Request,
    current: CurrentAccount,
    object_key: str,
) -> None:
    expected_prefix = (
        f"private/{current.account_type.value}/{current.account_id}/"
        "advertisement_image/"
    )
    if not object_key.startswith(expected_prefix):
        raise ApiError(
            400,
            "advertisement_image_invalid",
            "Reklama rasmini qayta yuklang.",
        )
    try:
        await asyncio.to_thread(
            request.app.state.r2.verify_profile_image,
            object_key,
        )
    except UploadRejected as exc:
        raise ApiError(
            400,
            "advertisement_image_invalid",
            str(exc),
        ) from None
    except Exception:
        raise ApiError(
            400,
            "advertisement_image_missing",
            "Reklama rasmi yuklanmadi. Rasmni qayta tanlang.",
        ) from None


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
    request: Request,
    current: CurrentWrite,
    service: ServiceDep,
) -> AdvertisementRead:
    """Reklama `payment_pending` bilan yaratiladi va hali ko'rinmaydi."""
    await verify_advertisement_image(
        request,
        current,
        body.desktop_image_object_key,
    )
    if body.mobile_image_object_key:
        await verify_advertisement_image(
            request,
            current,
            body.mobile_image_object_key,
        )
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
