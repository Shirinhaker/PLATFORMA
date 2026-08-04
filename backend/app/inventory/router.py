from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.accounts.model import AccountType
from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
)
from app.core.errors import ApiError
from app.inventory.schemas import (
    InventoryItemRead,
    InventoryItemWrite,
    InventoryListRead,
    ProductionBatchRead,
    RecipeIngredientRead,
    StockMoveCreate,
    StockMoveRead,
    StockMoveResult,
)
from app.inventory.service import InventoryService


router = APIRouter(prefix="/api/v1/warehouse", tags=["warehouse"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]


def inventory_service(request: Request) -> InventoryService:
    return request.app.state.inventory_service


InventoryServiceDep = Annotated[InventoryService, Depends(inventory_service)]


def _business_account_id(current: CurrentAccount) -> int:
    if current.account_type is not AccountType.BUSINESS:
        raise ApiError(
            403,
            "business_account_required",
            "Bu bo‘lim faqat biznes akkaunt uchun.",
        )
    return current.account_id


def _permissions(current: CurrentAccount) -> tuple[str, ...] | None:
    return current.permissions if current.actor_type == "staff" else None


@router.get("/items", response_model=InventoryListRead)
async def list_inventory_items(
    current: CurrentRead,
    service: InventoryServiceDep,
) -> InventoryListRead:
    return await service.list_items(
        business_account_id=_business_account_id(current),
        permissions=_permissions(current),
    )


@router.put("/items/{catalog_item_id}", response_model=InventoryItemRead)
async def configure_inventory_item(
    catalog_item_id: int,
    body: InventoryItemWrite,
    current: CurrentWrite,
    service: InventoryServiceDep,
) -> InventoryItemRead:
    return await service.configure_item(
        business_account_id=_business_account_id(current),
        permissions=_permissions(current),
        catalog_item_id=catalog_item_id,
        body=body,
    )


@router.post(
    "/moves",
    response_model=StockMoveResult,
    status_code=status.HTTP_201_CREATED,
)
async def create_stock_move(
    body: StockMoveCreate,
    current: CurrentWrite,
    service: InventoryServiceDep,
) -> StockMoveResult:
    return await service.create_move(
        business_account_id=_business_account_id(current),
        actor_staff_id=current.staff_id,
        permissions=_permissions(current),
        body=body,
        actor_name=current.name,
    )


@router.delete("/moves/{move_id}", status_code=204)
async def delete_stock_move(
    move_id: int,
    current: CurrentWrite,
    service: InventoryServiceDep,
) -> Response:
    await service.delete_move(
        business_account_id=_business_account_id(current),
        actor_staff_id=current.staff_id,
        permissions=_permissions(current),
        move_id=move_id,
    )
    return Response(status_code=204)


@router.get(
    "/items/{inventory_item_id}/moves",
    response_model=list[StockMoveRead],
)
async def list_stock_moves(
    inventory_item_id: int,
    current: CurrentRead,
    service: InventoryServiceDep,
) -> list[StockMoveRead]:
    return await service.list_moves(
        business_account_id=_business_account_id(current),
        permissions=_permissions(current),
        inventory_item_id=inventory_item_id,
    )


@router.get(
    "/items/{inventory_item_id}/recipe",
    response_model=list[RecipeIngredientRead],
)
async def get_recipe(
    inventory_item_id: int,
    current: CurrentRead,
    service: InventoryServiceDep,
) -> list[RecipeIngredientRead]:
    return await service.recipe(
        business_account_id=_business_account_id(current),
        permissions=_permissions(current),
        ready_inventory_item_id=inventory_item_id,
    )


@router.get("/production", response_model=list[ProductionBatchRead])
async def list_production_history(
    current: CurrentRead,
    service: InventoryServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ProductionBatchRead]:
    return await service.production_history(
        business_account_id=_business_account_id(current),
        permissions=_permissions(current),
        limit=limit,
    )
