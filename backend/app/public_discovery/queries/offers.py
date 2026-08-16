"""Tuman bo'yicha takliflar."""

from __future__ import annotations

import hashlib

from sqlalchemy import (
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.accounts.model import Account
from app.catalog.model import CatalogItem
from app.core.enums import ReviewState
from app.listings.model import Listing, ListingMedia
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile
from app.public_discovery.queries.constants import (
    ImageUrlProvider,
)
from app.public_discovery.queries.helpers import (
    build_listing_public_id,
    build_public_id,
)
from app.public_discovery.queries.location import (
    _location_contains,
)
from app.public_discovery.queries.subscriptions import (
    _active_home_offer_business_ids,
    _has_active_subscription,
)
from app.public_discovery.schemas import (
    PublicDistrictOffer,
    PublicDistrictOffersResponse,
    PublicResultKind,
)


async def load_public_district_offers(
    session: AsyncSession,
    *,
    district: str,
    slot: int,
    image_url_provider: ImageUrlProvider,
    include_listings: bool = False,
) -> PublicDistrictOffersResponse:
    if not district:
        return PublicDistrictOffersResponse(
            needs_district=True,
            items=[],
            slot=slot,
        )

    business_owner = aliased(UserProfile, name="district_offer_owner")
    statement = (
        select(CatalogItem, BusinessProfile)
        .join(
            BusinessProfile,
            BusinessProfile.account_id == CatalogItem.business_account_id,
        )
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
            CatalogItem.status == "active",
            CatalogItem.review_state == ReviewState.READY,
            CatalogItem.business_account_id.is_not(None),
            _location_contains(business_owner.district, district),
        )
        .order_by(CatalogItem.id)
    )
    catalog_rows = list((await session.execute(statement)).all())
    grouped: dict[
        int,
        tuple[
            BusinessProfile,
            list[tuple[str, CatalogItem | Listing]],
        ],
    ] = {}
    listing_rows: list[tuple[Listing, BusinessProfile]] = []
    if include_listings:
        listing_statement = (
            select(Listing, BusinessProfile)
            .join(
                BusinessProfile,
                BusinessProfile.account_id == Listing.owner_business_account_id,
            )
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
                Listing.status == "active",
                Listing.visibility == "all",
                Listing.review_state == ReviewState.READY,
                Listing.owner_business_account_id.is_not(None),
                _location_contains(business_owner.district, district),
            )
            .order_by(Listing.id)
        )
        listing_rows = list((await session.execute(listing_statement)).all())

    active_home_offer_business_ids = await _active_home_offer_business_ids(
        session,
        {business.account_id for _, business in [*catalog_rows, *listing_rows]},
    )
    for catalog_item, business in catalog_rows:
        if not _has_active_subscription(
            business,
            active_home_offer_business_ids,
            frozenset({"plus", "pro"}),
        ):
            continue
        grouped.setdefault(business.account_id, (business, []))[1].append(
            (catalog_item.kind, catalog_item)
        )

    if include_listings:
        for listing, business in listing_rows:
            if not _has_active_subscription(
                business,
                active_home_offer_business_ids,
                frozenset({"plus", "pro"}),
            ):
                continue
            grouped.setdefault(
                business.account_id,
                (business, []),
            )[1].append(("listing", listing))
    business_ids = sorted(grouped)
    if business_ids:
        seed = hashlib.sha256(district.casefold().encode("utf-8")).digest()
        offset = (int.from_bytes(seed[:8], "big") + slot) % len(business_ids)
        business_ids = (business_ids[offset:] + business_ids[:offset])[:20]

    selected: list[tuple[str, CatalogItem | Listing, BusinessProfile]] = []
    for business_id in business_ids:
        business, content_items = grouped[business_id]
        kinds = sorted({kind for kind, _ in content_items})
        selected_kind = kinds[(slot + business_id) % len(kinds)]
        candidates = [item for kind, item in content_items if kind == selected_kind]
        selected.append(
            (
                selected_kind,
                candidates[(slot // 3 + business_id) % len(candidates)],
                business,
            )
        )

    from app.catalog.repository import build_content_public_id

    items = []
    for kind, content, business in selected:
        if kind == "listing":
            media_key = await session.scalar(
                select(ListingMedia.object_key)
                .where(
                    ListingMedia.listing_id == content.id,
                    ListingMedia.media_type == "photo",
                )
                .order_by(ListingMedia.position, ListingMedia.id)
                .limit(1)
            )
            content_public_id = build_listing_public_id(content.id)
            title = content.title or "Taklif"
            price = content.price_text
            image = image_url_provider(media_key or "")
        else:
            content_public_id = build_content_public_id(kind, content.id)
            title = content.name or "Taklif"
            price = content.price_text
            image = image_url_provider(content.image_object_key)
        items.append(
            PublicDistrictOffer(
                kind=kind,
                business_id=business.account_id,
                business_public_id=build_public_id(
                    PublicResultKind.BUSINESS,
                    business.account_id,
                ),
                content_id=content.id,
                content_public_id=content_public_id,
                title=title,
                business_name=business.name,
                image=image,
                business_logo=image_url_provider(business.logo_object_key),
                price=price,
                unit="",
            )
        )
    return PublicDistrictOffersResponse(
        needs_district=False,
        items=items,
        slot=slot,
    )
