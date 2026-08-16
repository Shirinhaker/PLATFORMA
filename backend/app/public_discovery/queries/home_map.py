"""Bosh sahifa xaritasi."""

from __future__ import annotations

from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.accounts.model import Account
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile
from app.public_discovery.queries.constants import (
    ImageUrlProvider,
)
from app.public_discovery.queries.following import (
    load_followed_profiles,
)
from app.public_discovery.queries.helpers import (
    build_public_id,
)
from app.public_discovery.queries.location import (
    _location_contains,
)
from app.public_discovery.queries.subscriptions import (
    _active_pro_business_ids,
    _has_active_subscription,
)
from app.public_discovery.schemas import (
    PublicHomeBusinessPin,
    PublicHomeMapResponse,
    PublicHomeSpecialistPin,
    PublicResultKind,
)
from app.specialists.model import (
    SpecialistProfile,
)


async def load_public_home_map(
    session: AsyncSession,
    *,
    district: str,
    image_url_provider: ImageUrlProvider,
    account_id: int | None = None,
    account_type: str | None = None,
) -> PublicHomeMapResponse:
    if not district:
        return PublicHomeMapResponse(businesses=[], specialists=[])

    business_owner = aliased(UserProfile, name="home_map_business_owner")
    business_statement = (
        select(BusinessProfile)
        .join(Account, Account.id == BusinessProfile.account_id)
        .join(
            ProfileLink,
            ProfileLink.business_account_id == BusinessProfile.account_id,
        )
        .join(
            business_owner,
            business_owner.account_id == ProfileLink.user_account_id,
        )
        .where(
            Account.status == "active",
            BusinessProfile.latitude.is_not(None),
            BusinessProfile.longitude.is_not(None),
            _location_contains(business_owner.district, district),
        )
        .order_by(func.lower(BusinessProfile.name), BusinessProfile.account_id)
    )
    business_profiles = list((await session.scalars(business_statement)).all())
    active_pro_business_ids = await _active_pro_business_ids(
        session,
        {profile.account_id for profile in business_profiles},
    )

    followed = (
        await load_followed_profiles(
            session,
            account_id=account_id,
            account_type=account_type or "user",
            image_url_provider=image_url_provider,
        )
        if account_id is not None
        else []
    )
    followed_businesses = {
        item.public_id for item in followed if item.kind == "business"
    }
    followed_users = {item.public_id for item in followed if item.kind == "user"}

    specialist_profiles = []
    user_profiles_by_id: dict[int, UserProfile] = {}
    if followed_users:
        specialist_profiles = list(
            (
                await session.scalars(
                    select(SpecialistProfile)
                    .join(
                        UserProfile,
                        UserProfile.account_id == SpecialistProfile.user_account_id,
                    )
                    .join(Account, Account.id == UserProfile.account_id)
                    .where(
                        Account.status == "active",
                        SpecialistProfile.visible.is_(True),
                        SpecialistProfile.latitude.is_not(None),
                        SpecialistProfile.longitude.is_not(None),
                        _location_contains(UserProfile.district, district),
                    )
                    .order_by(
                        func.lower(UserProfile.name),
                        SpecialistProfile.user_account_id,
                    )
                )
            ).all()
        )
        specialist_user_ids = {row.user_account_id for row in specialist_profiles}
        if specialist_user_ids:
            user_profiles_by_id = {
                row.account_id: row
                for row in (
                    await session.scalars(
                        select(UserProfile).where(
                            UserProfile.account_id.in_(specialist_user_ids),
                        )
                    )
                ).all()
            }

    businesses = [
        PublicHomeBusinessPin(
            id=profile.account_id,
            public_id=build_public_id(
                PublicResultKind.BUSINESS,
                profile.account_id,
            ),
            name=profile.name or "Biznes",
            yon=profile.direction,
            tur=profile.activity_type,
            lat=profile.latitude,
            lng=profile.longitude,
            logo_file=image_url_provider(profile.logo_object_key),
            logo_x=profile.logo_x,
            logo_y=profile.logo_y,
            logo_zoom=profile.logo_zoom,
            address=profile.address,
            source="public",
        )
        for profile in business_profiles
        if build_public_id(
            PublicResultKind.BUSINESS,
            profile.account_id,
        )
        in followed_businesses
        or (
            profile.map_visible
            and _has_active_subscription(
                profile,
                active_pro_business_ids,
                frozenset({"pro"}),
            )
        )
    ]
    specialists = []
    for specialist in specialist_profiles:
        profile = user_profiles_by_id.get(specialist.user_account_id)
        if profile is None:
            continue
        public_id = build_public_id(
            PublicResultKind.USER,
            profile.account_id,
        )
        if public_id not in followed_users:
            continue
        specialists.append(
            PublicHomeSpecialistPin(
                user_id=profile.account_id,
                public_id=public_id,
                name=profile.name or "Foydalanuvchi",
                kasb=specialist.profession or "Mutaxasis",
                is_gov=specialist.is_government,
                lat=specialist.latitude,
                lng=specialist.longitude,
                avatar_file=image_url_provider(profile.avatar_object_key),
                avatar_x=profile.avatar_x,
                avatar_y=profile.avatar_y,
                avatar_zoom=profile.avatar_zoom,
                source="public",
            )
        )
    return PublicHomeMapResponse(
        businesses=businesses,
        specialists=specialists,
    )
