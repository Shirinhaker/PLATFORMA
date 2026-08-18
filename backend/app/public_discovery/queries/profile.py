"""Ochiq profil sahifasi va uning e'lonlari."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.catalog.model import CatalogGroup, CatalogItem
from app.core.enums import ReviewState
from app.listings.model import Listing, ListingMedia
from app.profiles.model import BusinessProfile, UserProfile
from app.public_discovery.queries.constants import (
    UZBEKISTAN_TZ,
    ImageUrlProvider,
    _cabinet_records,
)
from app.public_discovery.queries.helpers import (
    _bounded_integer,
    build_listing_public_id,
)
from app.public_discovery.schemas import (
    PublicProfileDetail,
    PublicProfileItem,
    PublicProfileListing,
    PublicSpecialistCredential,
    PublicSpecialistOffer,
    PublicSpecialistPortfolio,
    PublicSpecialistSummary,
)
from app.queues.repository_parts import active_provider_count, active_queue_count
from app.queues.service_parts.helpers import QUEUE_DIRECTIONS
from app.specialists.model import (
    SpecialistCredential,
    SpecialistOffer,
    SpecialistPortfolio,
    SpecialistProfile,
)


async def _resolve_public_profile_account_id(
    session: AsyncSession,
    *,
    kind: str,
    public_id: str,
) -> int | None:
    model = BusinessProfile if kind == "business" else UserProfile
    account_type = AccountType.BUSINESS if kind == "business" else AccountType.USER
    account_id = (
        await session.scalars(
            select(model.account_id)
            .join(Account, Account.id == model.account_id)
            .where(
                model.public_id == public_id,
                Account.status == "active",
                Account.account_type == account_type,
            )
            .limit(1)
        )
    ).first()
    return int(account_id) if account_id is not None else None


async def _load_public_listings(
    session: AsyncSession,
    *,
    account_id: int,
    kind: str,
    image_url_provider: ImageUrlProvider,
) -> list[PublicProfileListing]:
    media_key = (
        select(ListingMedia.object_key)
        .where(
            ListingMedia.listing_id == Listing.id,
            ListingMedia.media_type == "photo",
        )
        .order_by(ListingMedia.position, ListingMedia.id)
        .limit(1)
        .scalar_subquery()
    )
    owner_constraint = (
        Listing.owner_business_account_id == account_id
        if kind == "business"
        else (
            (Listing.owner_user_account_id == account_id)
            & (Listing.visibility == "all")
        )
    )
    rows = (
        await session.execute(
            select(Listing, media_key.label("image_object_key"))
            .where(
                owner_constraint,
                Listing.status == "active",
                Listing.review_state == ReviewState.READY,
            )
            .order_by(Listing.created_at.desc(), Listing.id.desc())
        )
    ).all()
    return [
        PublicProfileListing(
            public_id=build_listing_public_id(listing.id),
            title=listing.title or "E'lon",
            price_text=listing.price_text,
            description=listing.description,
            address=listing.address,
            image_url=image_url_provider(image_object_key or ""),
        )
        for listing, image_object_key in rows
    ]


async def load_public_profile(
    session: AsyncSession,
    *,
    kind: str,
    public_id: str,
    image_url_provider: ImageUrlProvider,
    include_listings: bool = True,
    queue_date: date | None = None,
) -> PublicProfileDetail | None:
    account_id = await _resolve_public_profile_account_id(
        session,
        kind=kind,
        public_id=public_id,
    )
    if account_id is None:
        return None

    listings = (
        await _load_public_listings(
            session,
            account_id=account_id,
            kind=kind,
            image_url_provider=image_url_provider,
        )
        if include_listings
        else []
    )
    if kind == "user":
        profile = await session.get(UserProfile, account_id)
        if profile is None:
            return None
        specialist = None
        specialist_profile = await session.get(SpecialistProfile, account_id)
        if specialist_profile is not None and specialist_profile.visible:
            credentials = list(
                (
                    await session.scalars(
                        select(SpecialistCredential)
                        .where(SpecialistCredential.user_account_id == account_id)
                        .order_by(
                            SpecialistCredential.position, SpecialistCredential.id
                        )
                    )
                ).all()
            )
            offers = list(
                (
                    await session.scalars(
                        select(SpecialistOffer)
                        .where(SpecialistOffer.user_account_id == account_id)
                        .order_by(SpecialistOffer.created_at, SpecialistOffer.id)
                    )
                ).all()
            )
            portfolio = list(
                (
                    await session.scalars(
                        select(SpecialistPortfolio)
                        .where(SpecialistPortfolio.user_account_id == account_id)
                        .order_by(
                            SpecialistPortfolio.created_at, SpecialistPortfolio.id
                        )
                    )
                ).all()
            )
            specialist = PublicSpecialistSummary(
                profession=specialist_profile.profession,
                description=specialist_profile.description,
                credentials=[
                    PublicSpecialistCredential(
                        id=row.id,
                        image_url=(
                            image_url_provider(row.object_key)
                            if row.object_key
                            else row.legacy_media_url
                        ),
                    )
                    for row in credentials
                ],
                offers=[
                    PublicSpecialistOffer(
                        id=row.id,
                        kind=row.kind,
                        name=row.name,
                        price_text=row.price_text,
                        note=row.note,
                        image_url=(
                            image_url_provider(row.image_object_key)
                            if row.image_object_key
                            else row.legacy_image_url
                        ),
                    )
                    for row in offers
                ],
                portfolio=[
                    PublicSpecialistPortfolio(
                        id=row.id,
                        media_type=row.media_type,
                        media_url=(
                            image_url_provider(row.object_key)
                            if row.object_key
                            else row.legacy_media_url
                        ),
                    )
                    for row in portfolio
                ],
            )
        return PublicProfileDetail(
            kind="user",
            public_id=public_id,
            name=profile.name or "Foydalanuvchi",
            public_username=profile.public_username,
            image_url=image_url_provider(profile.avatar_object_key),
            crop_x=profile.avatar_x,
            crop_y=profile.avatar_y,
            crop_zoom=profile.avatar_zoom,
            followers_count=max(0, profile.followers_count),
            specialist=specialist,
            listings=listings,
        )

    profile = await session.get(BusinessProfile, account_id)
    if profile is None:
        return None
    from app.catalog.repository import build_content_public_id

    course_rows_by_id: dict[str, dict[str, object]] = {}
    if str(profile.direction or "").strip() == "Ta'lim faoliyati":
        course_rows = await _cabinet_records.read_resource(
            session,
            account_id=account_id,
            account_type="business",
            resource="items",
        )
        if not course_rows:
            payload = (
                profile.cabinet_payload
                if isinstance(profile.cabinet_payload, dict)
                else {}
            )
            fallback = payload.get("items", [])
            course_rows = fallback if isinstance(fallback, list) else []
        course_rows_by_id = {
            str(row.get("id")): row
            for row in course_rows
            if isinstance(row, dict) and row.get("id") not in (None, "")
        }

    resolved_queue_date = queue_date or datetime.now(UZBEKISTAN_TZ).date()

    item_rows = (
        await session.execute(
            select(
                CatalogItem,
                CatalogGroup.name.label("group_name"),
                active_provider_count(
                    CatalogItem.id,
                    CatalogItem.business_account_id,
                ).label("queue_provider_count"),
                active_queue_count(
                    CatalogItem.id,
                    CatalogItem.business_account_id,
                    resolved_queue_date,
                ).label("today_queue_count"),
            )
            .outerjoin(
                CatalogGroup,
                CatalogGroup.id == CatalogItem.catalog_group_id,
            )
            .where(
                CatalogItem.business_account_id == account_id,
                CatalogItem.status == "active",
                CatalogItem.review_state == ReviewState.READY,
            )
            .order_by(CatalogItem.created_at.desc(), CatalogItem.id.desc())
        )
    ).all()
    items = []
    for (
        item,
        group_name,
        queue_provider_count,
        today_queue_count,
    ) in item_rows:
        source_key = str(item.source_record_key or "")
        course_row = course_rows_by_id.get(source_key, {})
        if not course_row and source_key.startswith("item:"):
            course_row = course_rows_by_id.get(
                source_key.removeprefix("item:"),
                {},
            )
        course_mode = str(course_row.get("course_mode") or "")
        if course_mode not in {"", "offline", "online", "hybrid"}:
            course_mode = "offline"
        course_level = str(course_row.get("course_level") or "")
        if course_level not in {"", "beginner", "intermediate", "advanced", "all"}:
            course_level = "all"
        enrollment_status = str(course_row.get("enrollment_status") or "open")
        if enrollment_status not in {"open", "closed"}:
            enrollment_status = "open"
        items.append(
            PublicProfileItem(
                kind=item.kind,
                public_id=build_content_public_id(item.kind, item.id),
                name=item.name,
                price_text=item.price_text,
                unit=item.unit or "dona",
                note=item.note,
                image_url=image_url_provider(item.image_object_key),
                group_name=group_name or "",
                queue_enabled=bool(item.queue_enabled),
                queue_provider_count=max(0, int(queue_provider_count or 0)),
                today_queue_count=max(0, int(today_queue_count or 0)),
                course_mode=course_mode,
                course_duration=str(course_row.get("course_duration") or "")[:80],
                lesson_duration=_bounded_integer(
                    course_row.get("lesson_duration"),
                    1440,
                ),
                age_from=_bounded_integer(course_row.get("age_from"), 120),
                age_to=_bounded_integer(course_row.get("age_to"), 120),
                course_level=course_level,
                enrollment_status=enrollment_status,
            )
        )
    queue_total = (
        sum(item.today_queue_count for item in items)
        if str(profile.direction or "").strip() in QUEUE_DIRECTIONS
        else 0
    )
    return PublicProfileDetail(
        kind="business",
        public_id=public_id,
        name=profile.name or "Do'kon",
        public_username=profile.public_username,
        description=profile.description,
        direction=profile.direction,
        activity_type=profile.activity_type,
        address=profile.address,
        phone=profile.phone,
        image_url=image_url_provider(profile.logo_object_key),
        crop_x=profile.logo_x,
        crop_y=profile.logo_y,
        crop_zoom=profile.logo_zoom,
        followers_count=max(0, profile.followers_count),
        queue_total=queue_total,
        items=items,
        listings=listings,
    )
