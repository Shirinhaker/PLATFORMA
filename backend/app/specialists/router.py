from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response, status

from app.accounts.model import AccountType
from app.auth.dependencies import CurrentAccount, require_csrf, require_current_account
from app.core.errors import ApiError
from app.specialists.schemas import (
    CreatedRead,
    MutationRead,
    SpecialistCredentialCreate,
    SpecialistOfferWrite,
    SpecialistPortfolioCreate,
    SpecialistProfileWrite,
    SpecialistRead,
)
from app.specialists.service import SpecialistService

router = APIRouter(prefix="/api/v1/specialists", tags=["specialists"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
RowId = Annotated[int, Path(ge=1)]


def service(request: Request) -> SpecialistService:
    return request.app.state.specialist_service


def _user_id(current: CurrentAccount) -> int:
    if current.account_type is not AccountType.USER or current.actor_type == "staff":
        raise ApiError(
            403,
            "user_account_required",
            "Bu bo‘lim faqat foydalanuvchi akkaunti uchun.",
        )
    return current.account_id


@router.get("/me", response_model=SpecialistRead)
async def get_my_specialist(request: Request, current: CurrentRead) -> SpecialistRead:
    return await service(request).get(user_account_id=_user_id(current))


@router.put("/me", response_model=SpecialistRead)
async def update_my_specialist(
    body: SpecialistProfileWrite,
    request: Request,
    current: CurrentWrite,
) -> SpecialistRead:
    return await service(request).update_profile(
        user_account_id=_user_id(current), body=body,
    )


@router.post("/me/credentials", response_model=CreatedRead, status_code=status.HTTP_201_CREATED)
async def add_credential(
    body: SpecialistCredentialCreate,
    request: Request,
    current: CurrentWrite,
) -> CreatedRead:
    return await service(request).add_credential(
        user_account_id=_user_id(current), body=body,
    )


@router.delete("/me/credentials/{row_id}", status_code=204)
async def delete_credential(row_id: RowId, request: Request, current: CurrentWrite) -> Response:
    await service(request).delete_credential(
        user_account_id=_user_id(current), row_id=row_id,
    )
    return Response(status_code=204)


@router.post("/me/offers", response_model=CreatedRead, status_code=status.HTTP_201_CREATED)
async def create_offer(
    body: SpecialistOfferWrite,
    request: Request,
    current: CurrentWrite,
) -> CreatedRead:
    return await service(request).create_offer(
        user_account_id=_user_id(current), body=body,
    )


@router.put("/me/offers/{row_id}", response_model=MutationRead)
async def update_offer(
    row_id: RowId,
    body: SpecialistOfferWrite,
    request: Request,
    current: CurrentWrite,
) -> MutationRead:
    return await service(request).update_offer(
        user_account_id=_user_id(current), row_id=row_id, body=body,
    )


@router.delete("/me/offers/{row_id}", status_code=204)
async def delete_offer(row_id: RowId, request: Request, current: CurrentWrite) -> Response:
    await service(request).delete_offer(
        user_account_id=_user_id(current), row_id=row_id,
    )
    return Response(status_code=204)


@router.post("/me/portfolio", response_model=CreatedRead, status_code=status.HTTP_201_CREATED)
async def add_portfolio(
    body: SpecialistPortfolioCreate,
    request: Request,
    current: CurrentWrite,
) -> CreatedRead:
    return await service(request).add_portfolio(
        user_account_id=_user_id(current), body=body,
    )


@router.delete("/me/portfolio/{row_id}", status_code=204)
async def delete_portfolio(row_id: RowId, request: Request, current: CurrentWrite) -> Response:
    await service(request).delete_portfolio(
        user_account_id=_user_id(current), row_id=row_id,
    )
    return Response(status_code=204)
