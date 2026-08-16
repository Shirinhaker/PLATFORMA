"""Kuzatilayotgan profillar."""

from __future__ import annotations

from sqlalchemy import (
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.follows.model import ProfileFollow
from app.profiles.model import BusinessProfile, UserProfile
from app.public_discovery.queries.constants import (
    ImageUrlProvider,
)
from app.public_discovery.queries.helpers import (
    build_public_id,
)
from app.public_discovery.schemas import (
    PublicFollowedProfile,
    PublicResultKind,
)


async def load_followed_profiles(
    session: AsyncSession,
    *,
    account_id: int,
    account_type: str,
    image_url_provider: ImageUrlProvider,
) -> list[PublicFollowedProfile]:
    """Obuna bo'lingan profillar — `profile_follows` jadvalidan.

    Ilgari ro'yxat kabinet JSON'idan o'qilib, eski identifikatorlar
    `legacy_id_map` orqali xaritalanardi. Obunalar endi o'z jadvalida,
    shuning uchun xaritalash kerak emas.
    """
    rows = list(
        (
            await session.scalars(
                select(ProfileFollow)
                .where(ProfileFollow.follower_account_id == account_id)
                .order_by(ProfileFollow.created_at.desc(), ProfileFollow.id.desc())
                .limit(500)
            )
        ).all()
    )
    result: list[PublicFollowedProfile] = []
    for row in rows:
        if row.target_kind == "business":
            business = await session.get(BusinessProfile, row.target_account_id)
            if business is None:
                continue
            result.append(
                PublicFollowedProfile(
                    kind="business",
                    public_id=build_public_id(
                        PublicResultKind.BUSINESS,
                        row.target_account_id,
                    ),
                    name=business.name,
                    image_url=image_url_provider(business.logo_object_key),
                    crop_x=business.logo_x,
                    crop_y=business.logo_y,
                    crop_zoom=business.logo_zoom,
                )
            )
            continue
        person = await session.get(UserProfile, row.target_account_id)
        if person is None:
            continue
        result.append(
            PublicFollowedProfile(
                kind="user",
                public_id=build_public_id(
                    PublicResultKind.USER,
                    row.target_account_id,
                ),
                name=person.name,
                image_url=image_url_provider(person.avatar_object_key),
                crop_x=person.avatar_x,
                crop_y=person.avatar_y,
                crop_zoom=person.avatar_zoom,
            )
        )
    return result
