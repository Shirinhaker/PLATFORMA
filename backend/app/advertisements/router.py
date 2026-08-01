from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request, Response

from app.advertisements.schemas import (
    PublicAdvertisement,
    PublicAdvertisementViews,
)


router = APIRouter(prefix="/api/v1/public", tags=["public-advertisements"])


@router.get(
    "/advertisements",
    response_model=list[PublicAdvertisement],
)
async def list_public_advertisements(
    request: Request,
    placement: str = Query(default="home", max_length=40),
    region: str = Query(default="", max_length=120),
    district: str = Query(default="", max_length=120),
) -> list[PublicAdvertisement]:
    return await request.app.state.advertisement_service.list_public(
        now=datetime.now(UTC),
        placement=placement,
        region=region.strip(),
        district=district.strip(),
    )


@router.post("/advertisements/views", status_code=204)
async def record_public_advertisement_views(
    request: Request,
    body: PublicAdvertisementViews,
) -> Response:
    await request.app.state.advertisement_service.record_public_views(
        list(dict.fromkeys(body.ids))
    )
    return Response(status_code=204)


@router.post("/advertisements/{public_id}/click", status_code=204)
async def record_public_advertisement_click(
    request: Request,
    public_id: Annotated[str, Path(pattern=r"^a_[0-9a-f]{16}$")],
) -> Response:
    await request.app.state.advertisement_service.record_public_click(
        public_id
    )
    return Response(status_code=204)
