from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.auth.dependencies import CurrentAccount, require_current_account

from app.public_discovery.schemas import (
    PublicDistrictOffersResponse,
    PublicFollowedProfile,
    PublicHomeMapResponse,
    PublicSearchParams,
    PublicSearchResponse,
)


router = APIRouter(prefix="/api/v1/public", tags=["public"])


async def optional_current_account(
    request: Request,
) -> CurrentAccount | None:
    session_token = request.cookies.get(
        request.app.state.settings.auth_cookie_name
    )
    if not session_token:
        return None
    identity = await request.app.state.auth_service.resolve_session(
        session_token,
        datetime.now(UTC),
    )
    if identity is None:
        return None
    return CurrentAccount(
        account_id=identity.account_id,
        account_type=identity.account_type,
        session_token=session_token,
    )


@router.get("/search", response_model=PublicSearchResponse, response_model_exclude_none=True)
async def search_public_profiles(
    request: Request,
    params: Annotated[PublicSearchParams, Query()],
) -> PublicSearchResponse:
    return await request.app.state.public_discovery_service.search(params)


@router.get("/home/map", response_model=PublicHomeMapResponse)
async def get_public_home_map(
    request: Request,
    district: str = Query(min_length=1, max_length=120),
    current: CurrentAccount | None = Depends(optional_current_account),
) -> PublicHomeMapResponse:
    return await request.app.state.public_discovery_service.home_map(
        district.strip(),
        account_id=current.account_id if current else None,
        account_type=current.account_type.value if current else None,
    )


@router.get(
    "/home/district-offers",
    response_model=PublicDistrictOffersResponse,
)
async def get_public_district_offers(
    request: Request,
    district: str = Query(min_length=1, max_length=120),
) -> PublicDistrictOffersResponse:
    return await request.app.state.public_discovery_service.district_offers(
        district.strip()
    )


@router.get(
    "/home/followed-profiles",
    response_model=list[PublicFollowedProfile],
)
async def get_public_home_followed_profiles(
    request: Request,
    current: CurrentAccount = Depends(require_current_account),
) -> list[PublicFollowedProfile]:
    return await request.app.state.public_discovery_service.followed_profiles(
        account_id=current.account_id,
        account_type=current.account_type.value,
    )
