from collections.abc import AsyncIterator
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import AccountType
from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
)
from app.core.errors import ApiError
from app.profiles.repository import (
    get_business_profile,
    get_user_profile,
    patch_business_profile,
    patch_user_profile,
)
from app.profiles.schemas import (
    BusinessProfilePatch,
    BusinessProfileRead,
    MeRead,
    ProfileImageAttachment,
    UserProfilePatch,
    UserProfileRead,
)


router = APIRouter(prefix="/api/v1", tags=["profiles"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]


async def profile_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.session() as session:
        yield session


ProfileSession = Annotated[AsyncSession, Depends(profile_session)]


def require_account_type(
    current: CurrentAccount,
    expected: AccountType,
) -> None:
    if current.account_type is not expected:
        raise ApiError(
            403,
            "profile_type_forbidden",
            "Bu profil turiga kirish mumkin emas.",
        )


def user_profile_complete(profile) -> bool:
    return bool(profile.name.strip() and profile.phone.strip())


def business_profile_complete(profile) -> bool:
    return bool(
        profile.name.strip()
        and profile.phone.strip()
        and profile.direction.strip()
        and profile.address.strip()
    )


def require_profile_object_key(
    object_key: str,
    *,
    account_type: AccountType,
    account_id: int,
    purpose: str,
) -> None:
    prefix = (
        f"private/{account_type.value}/{account_id}/{purpose}/"
    )
    allowed = re.fullmatch(
        re.escape(prefix) + r"[0-9a-f]{32}\.(?:jpg|png|webp|gif)",
        object_key,
    )
    if allowed is None:
        raise ApiError(
            403,
            "media_object_forbidden",
            "Bu media obyekti akkauntga tegishli emas.",
        )


@router.get("/me", response_model=MeRead)
async def get_me(
    current: CurrentRead,
    session: ProfileSession,
) -> MeRead:
    if current.account_type is AccountType.USER:
        profile = await get_user_profile(session, current.account_id)
        complete = user_profile_complete(profile)
    else:
        profile = await get_business_profile(session, current.account_id)
        complete = business_profile_complete(profile)
    return MeRead(
        account_id=current.account_id,
        account_type=current.account_type,
        name=profile.name,
        profile_complete=complete,
    )


@router.get("/user-profile", response_model=UserProfileRead)
async def read_user_profile(
    current: CurrentRead,
    session: ProfileSession,
):
    require_account_type(current, AccountType.USER)
    return await get_user_profile(session, current.account_id)


@router.put("/user-profile", response_model=UserProfileRead)
async def update_user_profile(
    body: UserProfilePatch,
    current: CurrentWrite,
    session: ProfileSession,
):
    require_account_type(current, AccountType.USER)
    try:
        profile = await get_user_profile(session, current.account_id)
        await patch_user_profile(session, profile, body)
        await session.commit()
        return profile
    except Exception:
        await session.rollback()
        raise


@router.get("/business-profile", response_model=BusinessProfileRead)
async def read_business_profile(
    current: CurrentRead,
    session: ProfileSession,
):
    require_account_type(current, AccountType.BUSINESS)
    return await get_business_profile(session, current.account_id)


@router.put("/business-profile", response_model=BusinessProfileRead)
async def update_business_profile(
    body: BusinessProfilePatch,
    current: CurrentWrite,
    session: ProfileSession,
):
    require_account_type(current, AccountType.BUSINESS)
    try:
        profile = await get_business_profile(session, current.account_id)
        await patch_business_profile(session, profile, body)
        await session.commit()
        return profile
    except Exception:
        await session.rollback()
        raise


@router.put("/user-profile/avatar", response_model=UserProfileRead)
async def attach_user_avatar(
    body: ProfileImageAttachment,
    current: CurrentWrite,
    session: ProfileSession,
):
    require_account_type(current, AccountType.USER)
    require_profile_object_key(
        body.object_key,
        account_type=AccountType.USER,
        account_id=current.account_id,
        purpose="avatar",
    )
    try:
        profile = await get_user_profile(session, current.account_id)
        profile.avatar_object_key = body.object_key
        profile.avatar_x = body.x
        profile.avatar_y = body.y
        profile.avatar_zoom = body.zoom
        await session.flush()
        await session.commit()
        return profile
    except Exception:
        await session.rollback()
        raise


@router.put("/business-profile/logo", response_model=BusinessProfileRead)
async def attach_business_logo(
    body: ProfileImageAttachment,
    current: CurrentWrite,
    session: ProfileSession,
):
    require_account_type(current, AccountType.BUSINESS)
    require_profile_object_key(
        body.object_key,
        account_type=AccountType.BUSINESS,
        account_id=current.account_id,
        purpose="logo",
    )
    try:
        profile = await get_business_profile(session, current.account_id)
        profile.logo_object_key = body.object_key
        profile.logo_x = body.x
        profile.logo_y = body.y
        profile.logo_zoom = body.zoom
        await session.flush()
        await session.commit()
        return profile
    except Exception:
        await session.rollback()
        raise
