from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from app.auth.dependencies import (
    CurrentAccount,
    require_current_account,
    require_staff_permission,
)
from app.cache.rate_limit import consume_rate_limit
from app.core.errors import ApiError
from app.public_discovery.schemas import (
    PublicDistrictOffersResponse,
    PublicFollowedProfile,
    PublicHomeMapResponse,
    PublicProfileDetail,
    PublicSearchParams,
    PublicSearchResponse,
)


router = APIRouter(prefix="/api/v1/public", tags=["public"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def _redis(request: Request):
    wrapper = getattr(request.app.state, "redis", None)
    if wrapper is None:
        if request.app.state.settings.environment == "test":
            return None
        raise RuntimeError("redis_not_initialized")
    client = getattr(wrapper, "client", None)
    return client if client is not None and not callable(client) else wrapper


async def _enforce_public_rate_limit(
    request: Request,
    scope: str,
    *,
    limit: int,
    window_seconds: int = 60,
) -> None:
    redis = _redis(request)
    if redis is None:
        return
    result = await consume_rate_limit(
        redis,
        f"public:{scope}:ip:{_client_ip(request)}",
        limit,
        window_seconds,
    )
    if not result.allowed:
        raise ApiError(
            429,
            "public_rate_limited",
            "Juda ko‘p so‘rov yuborildi. Birozdan keyin qayta urinib ko‘ring.",
            headers={"Retry-After": str(result.retry_after_seconds)},
        )


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
    await _enforce_public_rate_limit(request, "search", limit=60)
    if params.page > 200:
        raise ApiError(
            400,
            "public_search_page_too_deep",
            "Qidiruv sahifasi juda uzoq. Filtr yoki aniqroq qidiruvdan foydalaning.",
        )
    return await request.app.state.public_discovery_service.search(params)


@router.get("/home/map", response_model=PublicHomeMapResponse)
async def get_public_home_map(
    request: Request,
    district: str = Query(min_length=1, max_length=120),
    current: CurrentAccount | None = Depends(optional_current_account),
) -> PublicHomeMapResponse:
    await _enforce_public_rate_limit(request, "home-map", limit=120)
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
    await _enforce_public_rate_limit(request, "district-offers", limit=120)
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
    require_staff_permission(current, "__business_owner__")
    return await request.app.state.public_discovery_service.followed_profiles(
        account_id=current.account_id,
        account_type=current.account_type.value,
    )


@router.get(
    "/profiles/{kind}/{public_id}",
    response_model=PublicProfileDetail,
)
async def get_public_profile(
    request: Request,
    kind: Literal["user", "business"],
    public_id: Annotated[
        str,
        Path(pattern=r"^[ub]_[0-9a-f]{16}$"),
    ],
) -> PublicProfileDetail:
    await _enforce_public_rate_limit(request, "profile", limit=120)
    profile = await request.app.state.public_discovery_service.profile(
        kind=kind,
        public_id=public_id,
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Profil topilmadi.")
    return profile
