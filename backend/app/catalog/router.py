from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.catalog.schemas import (
    PublicCatalogItem,
    PublicCatalogParams,
    PublicCatalogResponse,
)
from app.core.errors import ApiError


router = APIRouter(
    prefix="/api/v1/public/catalog",
    tags=["public-catalog"],
)


def _require_enabled(request: Request) -> None:
    if not request.app.state.settings.phase3c_public_enabled:
        raise ApiError(
            404,
            "feature_not_available",
            "Mahsulot va xizmatlar katalogi hozircha ochilmagan.",
        )


@router.get("/items", response_model=PublicCatalogResponse)
async def list_catalog_items(
    request: Request,
    params: Annotated[PublicCatalogParams, Query()],
) -> PublicCatalogResponse:
    _require_enabled(request)
    return await request.app.state.catalog_service.list_items(params)


@router.get("/items/{public_id}", response_model=PublicCatalogItem)
async def get_catalog_item(
    request: Request,
    public_id: str,
) -> PublicCatalogItem:
    _require_enabled(request)
    item = await request.app.state.catalog_service.get_item(public_id)
    if item is None:
        raise ApiError(
            404,
            "catalog_item_not_found",
            "Mahsulot yoki xizmat topilmadi.",
        )
    return item

