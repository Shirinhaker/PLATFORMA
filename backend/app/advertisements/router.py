from datetime import UTC, datetime

from fastapi import APIRouter, Query, Request

from app.advertisements.schemas import PublicAdvertisement


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

