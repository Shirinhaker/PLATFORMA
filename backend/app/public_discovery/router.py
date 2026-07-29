from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.public_discovery.schemas import (
    PublicSearchParams,
    PublicSearchResponse,
)


router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.get("/search", response_model=PublicSearchResponse, response_model_exclude_none=True)
async def search_public_profiles(
    request: Request,
    params: Annotated[PublicSearchParams, Query()],
) -> PublicSearchResponse:
    return await request.app.state.public_discovery_service.search(params)
