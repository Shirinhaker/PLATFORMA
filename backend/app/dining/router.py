"""Ovqatlanish zanjiri endpointlari.

Yo'llar v1656 (`/api/dining/...`) bilan bir xil tartibda, faqat yangi
`/api/v1` prefiksi ostida.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response, status

from app.accounts.model import AccountType
from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
)
from app.core.errors import ApiError
from app.dining.schemas import (
    DiningBookingCreate,
    DiningCancel,
    DiningCashierItemsUpdate,
    DiningItemsAdd,
    DiningKitchenUpdate,
    DiningOrderCreate,
    DiningOrderRead,
    DiningPaymentCreate,
    DiningPaymentResult,
    DiningPlaceMove,
    DiningPlaceRead,
    DiningPlaceWrite,
    DiningProblemOpen,
)
from app.dining.service import DiningService


router = APIRouter(prefix="/api/v1/dining", tags=["dining"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
PlaceId = Annotated[int, Path(gt=0)]
OrderId = Annotated[int, Path(gt=0)]


def dining_service(request: Request) -> DiningService:
    return request.app.state.dining_service


ServiceDep = Annotated[DiningService, Depends(dining_service)]


def _business_id(current: CurrentAccount) -> int:
    if current.account_type is not AccountType.BUSINESS:
        raise ApiError(
            403,
            "business_account_required",
            "Bu bo‘lim faqat biznes akkaunt uchun.",
        )
    return current.account_id


def _permissions(current: CurrentAccount) -> tuple[str, ...] | None:
    """Rahbar uchun `None` — u barcha bo'limlarni ko'radi."""
    return current.permissions if current.actor_type == "staff" else None


# ------------------------------------------------------------------ stollar


@router.get("/places", response_model=list[DiningPlaceRead])
async def list_dining_places(
    current: CurrentRead,
    service: ServiceDep,
) -> list[DiningPlaceRead]:
    return await service.list_places(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
    )


@router.post(
    "/places",
    response_model=DiningPlaceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_dining_place(
    body: DiningPlaceWrite,
    current: CurrentWrite,
    service: ServiceDep,
) -> DiningPlaceRead:
    return await service.create_place(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        body=body,
    )


@router.put("/places/{place_id}", response_model=DiningPlaceRead)
async def update_dining_place(
    place_id: PlaceId,
    body: DiningPlaceWrite,
    current: CurrentWrite,
    service: ServiceDep,
) -> DiningPlaceRead:
    return await service.update_place(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        place_id=place_id,
        body=body,
    )


@router.put("/places/{place_id}/position", response_model=DiningPlaceRead)
async def move_dining_place(
    place_id: PlaceId,
    body: DiningPlaceMove,
    current: CurrentWrite,
    service: ServiceDep,
) -> DiningPlaceRead:
    """Zal rejasida stolni surish — butun yozuvni yubormaydi."""
    return await service.update_place(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        place_id=place_id,
        body=body,
    )


@router.delete("/places/{place_id}", status_code=204)
async def delete_dining_place(
    place_id: PlaceId,
    current: CurrentWrite,
    service: ServiceDep,
) -> Response:
    await service.delete_place(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        place_id=place_id,
    )
    return Response(status_code=204)


@router.post("/places/{place_id}/clear", status_code=204)
async def clear_dining_place(
    place_id: PlaceId,
    current: CurrentWrite,
    service: ServiceDep,
) -> Response:
    await service.clear_place(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        place_id=place_id,
    )
    return Response(status_code=204)


@router.post(
    "/places/{place_id}/booking",
    response_model=DiningOrderRead,
    status_code=status.HTTP_201_CREATED,
)
async def book_dining_place(
    place_id: PlaceId,
    body: DiningBookingCreate,
    current: CurrentWrite,
    service: ServiceDep,
) -> DiningOrderRead:
    return await service.book(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        place_id=place_id,
        body=body,
    )


@router.post(
    "/places/{place_id}/order",
    response_model=DiningOrderRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_dining_order(
    place_id: PlaceId,
    body: DiningOrderCreate,
    current: CurrentWrite,
    service: ServiceDep,
) -> DiningOrderRead:
    return await service.create_order(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        place_id=place_id,
        actor_staff_id=current.staff_id,
        body=body,
    )


# ----------------------------------------------------------------- zakazlar


@router.get("/orders", response_model=list[DiningOrderRead])
async def list_dining_orders(
    current: CurrentRead,
    service: ServiceDep,
) -> list[DiningOrderRead]:
    return await service.list_orders(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
    )


@router.post("/orders/{order_id}/items", response_model=DiningOrderRead)
async def add_dining_order_items(
    order_id: OrderId,
    body: DiningItemsAdd,
    current: CurrentWrite,
    service: ServiceDep,
) -> DiningOrderRead:
    return await service.add_items(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        order_id=order_id,
        body=body,
    )


@router.put("/orders/{order_id}/kitchen", response_model=DiningOrderRead)
async def set_dining_kitchen_status(
    order_id: OrderId,
    body: DiningKitchenUpdate,
    current: CurrentWrite,
    service: ServiceDep,
) -> DiningOrderRead:
    """Oshpaz taomni tayyor deb belgilaydi."""
    return await service.set_kitchen_status(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        order_id=order_id,
        body=body,
    )


@router.post("/orders/{order_id}/payment", response_model=DiningPaymentResult)
async def confirm_dining_payment(
    order_id: OrderId,
    body: DiningPaymentCreate,
    current: CurrentWrite,
    service: ServiceDep,
) -> DiningPaymentResult:
    """Kassir to'lovni tasdiqlaydi; ombor va kassa shu payt yoziladi."""
    return await service.confirm_payment(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        order_id=order_id,
        actor_staff_id=current.staff_id,
        body=body,
    )


@router.put("/orders/{order_id}/cashier-items", response_model=DiningOrderRead)
async def update_dining_cashier_items(
    order_id: OrderId,
    body: DiningCashierItemsUpdate,
    current: CurrentWrite,
    service: ServiceDep,
) -> DiningOrderRead:
    return await service.update_cashier_items(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        order_id=order_id,
        body=body,
    )


@router.post("/orders/{order_id}/finalize", response_model=DiningOrderRead)
async def finalize_dining_order(
    order_id: OrderId,
    current: CurrentWrite,
    service: ServiceDep,
) -> DiningOrderRead:
    return await service.finalize(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        order_id=order_id,
    )


@router.post("/orders/{order_id}/cancel", response_model=DiningOrderRead)
async def cancel_dining_order(
    order_id: OrderId,
    body: DiningCancel,
    current: CurrentWrite,
    service: ServiceDep,
) -> DiningOrderRead:
    return await service.cancel(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        order_id=order_id,
        body=body,
    )


@router.post("/orders/{order_id}/problem", response_model=DiningOrderRead)
async def open_dining_problem(
    order_id: OrderId,
    body: DiningProblemOpen,
    current: CurrentWrite,
    service: ServiceDep,
) -> DiningOrderRead:
    return await service.open_problem(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        order_id=order_id,
        body=body,
    )


@router.post(
    "/orders/{order_id}/problem/resolve", response_model=DiningOrderRead
)
async def resolve_dining_problem(
    order_id: OrderId,
    current: CurrentWrite,
    service: ServiceDep,
) -> DiningOrderRead:
    return await service.resolve_problem(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        order_id=order_id,
    )
