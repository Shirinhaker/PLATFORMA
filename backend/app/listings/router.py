from fastapi import APIRouter, Request

from app.core.errors import ApiError


router = APIRouter(prefix="/api/v1/public", tags=["public-listings"])


@router.get("/listings")
async def list_public_listings(request: Request):
    if not request.app.state.settings.listings_enabled:
        raise ApiError(
            404,
            "feature_not_available",
            "E’lonlar hozircha ochilmagan.",
        )
    return await request.app.state.listing_service.list_public()

