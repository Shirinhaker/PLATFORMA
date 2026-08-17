from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request

from app.accounts.model import AccountType
from app.auth.dependencies import CurrentAccount, require_csrf, require_current_account
from app.core.errors import ApiError
from app.taxi.schemas import (
    AvailabilityWrite,
    DriverRead,
    DriverRidesRead,
    DriverWrite,
    MyRidesRead,
    PricingRead,
    RideAccepted,
    RideCreate,
    RideMutationRead,
    RideProgressWrite,
    RideRead,
    RideStatusWrite,
)
from app.taxi.service_parts import TaxiService

CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
RideId = Annotated[int, Path(gt=0)]


def service(request: Request) -> TaxiService:
    return request.app.state.taxi_service


def require_user_owner(current: CurrentAccount) -> None:
    if (
        current.account_type is not AccountType.USER
        or current.actor_type != "owner"
        or current.staff_id is not None
    ):
        raise ApiError(
            403, "user_owner_required", "Bu amal faqat oddiy profil egasi uchun."
        )


def require_enabled(request: Request) -> None:
    if not request.app.state.settings.taxi_enabled:
        raise ApiError(
            404,
            "feature_not_available",
            "Taxi chaqirish hozircha ochilmagan.",
        )


router = APIRouter(
    prefix="/api/v1/taxi",
    tags=["taxi"],
    dependencies=[Depends(require_enabled)],
)


@router.get("/pricing", response_model=PricingRead)
async def pricing(current: CurrentRead):
    require_user_owner(current)
    return TaxiService.pricing()


@router.get("/driver", response_model=DriverRead)
async def driver_profile(request: Request, current: CurrentRead):
    require_user_owner(current)
    return await service(request).get_driver(user_account_id=current.account_id)


@router.post("/driver", response_model=DriverRead)
async def save_driver(body: DriverWrite, request: Request, current: CurrentWrite):
    require_user_owner(current)
    return await service(request).save_driver(
        user_account_id=current.account_id,
        body=body,
    )


@router.put("/driver/available", response_model=DriverRead)
async def set_driver_available(
    body: AvailabilityWrite, request: Request, current: CurrentWrite
):
    require_user_owner(current)
    return await service(request).set_availability(
        user_account_id=current.account_id,
        available=body.available,
    )


@router.post("/rides", response_model=RideRead, status_code=201)
async def create_ride(body: RideCreate, request: Request, current: CurrentWrite):
    require_user_owner(current)
    return await service(request).create_ride(
        customer_account_id=current.account_id,
        body=body,
    )


@router.get("/rides/my", response_model=MyRidesRead)
async def my_rides(request: Request, current: CurrentRead):
    require_user_owner(current)
    return await service(request).my_rides(customer_account_id=current.account_id)


@router.post("/rides/{ride_id}/cancel", response_model=RideMutationRead)
async def cancel_ride(ride_id: RideId, request: Request, current: CurrentWrite):
    require_user_owner(current)
    return await service(request).cancel_ride(
        customer_account_id=current.account_id,
        ride_id=ride_id,
    )


@router.get("/rides/pending", response_model=DriverRidesRead)
async def pending_rides(request: Request, current: CurrentRead):
    require_user_owner(current)
    return await service(request).pending_rides(user_account_id=current.account_id)


@router.post("/rides/{ride_id}/accept", response_model=RideAccepted)
async def accept_ride(ride_id: RideId, request: Request, current: CurrentWrite):
    require_user_owner(current)
    return await service(request).accept_ride(
        user_account_id=current.account_id,
        ride_id=ride_id,
    )


@router.post("/rides/{ride_id}/status", response_model=RideMutationRead)
async def update_ride_status(
    ride_id: RideId,
    body: RideStatusWrite,
    request: Request,
    current: CurrentWrite,
):
    require_user_owner(current)
    return await service(request).update_status(
        user_account_id=current.account_id,
        ride_id=ride_id,
        new_status=body.status,
    )


@router.post("/rides/{ride_id}/progress", response_model=RideRead)
async def update_ride_progress(
    ride_id: RideId,
    body: RideProgressWrite,
    request: Request,
    current: CurrentWrite,
):
    require_user_owner(current)
    return await service(request).update_progress(
        user_account_id=current.account_id,
        ride_id=ride_id,
        km=body.km,
    )
