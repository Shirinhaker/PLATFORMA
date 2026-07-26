from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.profiles.model import BusinessProfile, UserProfile
from app.profiles.schemas import BusinessProfilePatch, UserProfilePatch


PROFILE_NOT_FOUND = ApiError(
    404,
    "profile_not_found",
    "Profil topilmadi.",
)
USERNAME_TAKEN = ApiError(
    409,
    "username_taken",
    "Bu username band.",
)


async def get_user_profile(
    session: AsyncSession,
    account_id: int,
) -> UserProfile:
    profile = await session.get(UserProfile, account_id)
    if profile is None:
        raise PROFILE_NOT_FOUND
    return profile


async def get_business_profile(
    session: AsyncSession,
    account_id: int,
) -> BusinessProfile:
    profile = await session.get(BusinessProfile, account_id)
    if profile is None:
        raise PROFILE_NOT_FOUND
    return profile


async def patch_user_profile(
    session: AsyncSession,
    profile: UserProfile,
    patch: UserProfilePatch,
) -> UserProfile:
    for field in patch.model_fields_set:
        setattr(profile, field, getattr(patch, field))
    try:
        await session.flush()
    except IntegrityError:
        if "public_username" in patch.model_fields_set:
            raise USERNAME_TAKEN from None
        raise
    return profile


async def patch_business_profile(
    session: AsyncSession,
    profile: BusinessProfile,
    patch: BusinessProfilePatch,
) -> BusinessProfile:
    for field in patch.model_fields_set:
        setattr(profile, field, getattr(patch, field))
    try:
        await session.flush()
    except IntegrityError:
        if "public_username" in patch.model_fields_set:
            raise USERNAME_TAKEN from None
        raise
    return profile
