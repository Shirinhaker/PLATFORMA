"""Qidiruv SQL so'rovlari: foydalanuvchi, biznes, kontent, e'lon."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    String,
    and_,
    case,
    cast,
    func,
    literal,
    or_,
    select,
    union_all,
)
from sqlalchemy.orm import aliased

from app.accounts.model import Account
from app.catalog.model import CatalogItem
from app.core.enums import ReviewState
from app.listings.model import Listing, ListingMedia
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile
from app.public_discovery.queries.helpers import (
    _contains,
    _empty,
)
from app.public_discovery.queries.location import (
    _location_constraints,
)
from app.public_discovery.schemas import (
    PublicResultKind,
    PublicResultType,
    PublicSearchParams,
)
from app.specialists.model import (
    SpecialistProfile,
)


def _user_query(params: PublicSearchParams):
    statement = (
        select(
            literal(PublicResultKind.USER.value).label("kind"),
            Account.id.label("account_id"),
            UserProfile.name.label("name"),
            UserProfile.public_username.label("public_username"),
            func.coalesce(SpecialistProfile.description, "").label("description"),
            _empty("direction"),
            _empty("activity_type"),
            UserProfile.region.label("region"),
            UserProfile.district.label("district"),
            UserProfile.mahalla.label("mahalla"),
            UserProfile.avatar_object_key.label("image_object_key"),
            literal(None).cast(String).label("price_text"),
            literal(None).cast(String).label("owner_state"),
            literal(None).cast(String).label("owner_label"),
            literal(None).cast(BigInteger).label("owner_business_account_id"),
            literal(None).cast(Boolean).label("can_order"),
            literal(None).cast(Boolean).label("can_chat"),
            literal(None).cast(BigInteger).label("map_business_account_id"),
            literal(None).cast(String).label("map_business_name"),
            literal(None).cast(Float).label("map_latitude"),
            literal(None).cast(Float).label("map_longitude"),
            literal(None).cast(String).label("map_owner_kind"),
        )
        .join(UserProfile, UserProfile.account_id == Account.id)
        .outerjoin(
            SpecialistProfile,
            and_(
                SpecialistProfile.user_account_id == UserProfile.account_id,
                SpecialistProfile.visible.is_(True),
            ),
        )
        .where(Account.status == "active")
    )

    if params.q:
        statement = statement.where(
            or_(
                _contains(UserProfile.name, params.q),
                _contains(UserProfile.public_username, params.q),
                _contains(SpecialistProfile.profession, params.q),
                _contains(SpecialistProfile.description, params.q),
            )
        )
    statement = statement.where(
        *_location_constraints(
            UserProfile.region,
            UserProfile.district,
            UserProfile.mahalla,
            params,
        )
    )
    return statement


def _business_query(params: PublicSearchParams):
    owner_profile = aliased(UserProfile, name="business_owner_profile")
    location_filtered = bool(params.region or params.district or params.mahalla)
    map_available = BusinessProfile.latitude.is_not(
        None
    ) & BusinessProfile.longitude.is_not(None)
    statement = select(
        literal(PublicResultKind.BUSINESS.value).label("kind"),
        Account.id.label("account_id"),
        BusinessProfile.name.label("name"),
        BusinessProfile.public_username.label("public_username"),
        BusinessProfile.description.label("description"),
        BusinessProfile.direction.label("direction"),
        BusinessProfile.activity_type.label("activity_type"),
        (
            owner_profile.region.label("region")
            if location_filtered
            else _empty("region")
        ),
        (
            owner_profile.district.label("district")
            if location_filtered
            else _empty("district")
        ),
        (
            owner_profile.mahalla.label("mahalla")
            if location_filtered
            else _empty("mahalla")
        ),
        BusinessProfile.logo_object_key.label("image_object_key"),
        literal(None).cast(String).label("price_text"),
        literal(None).cast(String).label("owner_state"),
        literal(None).cast(String).label("owner_label"),
        literal(None).cast(BigInteger).label("owner_business_account_id"),
        literal(None).cast(Boolean).label("can_order"),
        literal(None).cast(Boolean).label("can_chat"),
        case(
            (map_available, BusinessProfile.account_id),
            else_=None,
        ).label("map_business_account_id"),
        case(
            (map_available, BusinessProfile.name),
            else_=None,
        ).label("map_business_name"),
        case(
            (map_available, BusinessProfile.latitude),
            else_=None,
        ).label("map_latitude"),
        case(
            (map_available, BusinessProfile.longitude),
            else_=None,
        ).label("map_longitude"),
        literal(PublicResultKind.BUSINESS.value).label("map_owner_kind"),
    ).join(BusinessProfile, BusinessProfile.account_id == Account.id)
    if location_filtered:
        statement = statement.outerjoin(
            ProfileLink,
            ProfileLink.business_account_id == BusinessProfile.account_id,
        ).outerjoin(
            owner_profile,
            owner_profile.account_id == ProfileLink.user_account_id,
        )
    statement = statement.where(Account.status == "active")

    if params.q:
        statement = statement.where(
            or_(
                _contains(BusinessProfile.name, params.q),
                _contains(BusinessProfile.public_username, params.q),
                _contains(BusinessProfile.description, params.q),
                _contains(BusinessProfile.direction, params.q),
                _contains(BusinessProfile.activity_type, params.q),
            )
        )
    for column, value in (
        (BusinessProfile.direction, params.direction),
        (BusinessProfile.activity_type, params.activity_type),
    ):
        if value:
            statement = statement.where(_contains(column, value))

    statement = statement.where(
        *_location_constraints(
            owner_profile.region,
            owner_profile.district,
            owner_profile.mahalla,
            params,
        )
    )
    return statement


def _content_query(params: PublicSearchParams, kind: str):
    owner_profile = aliased(UserProfile, name=f"{kind}_owner_profile")
    owner_filtered = bool(
        params.direction
        or params.activity_type
        or params.region
        or params.district
        or params.mahalla
    )
    linked = (
        CatalogItem.owner_state == "linked"
    ) & CatalogItem.business_account_id.is_not(None)
    map_available = (
        linked
        & BusinessProfile.latitude.is_not(None)
        & BusinessProfile.longitude.is_not(None)
    )
    statement = select(
        literal(kind).label("kind"),
        CatalogItem.id.label("account_id"),
        CatalogItem.name.label("name"),
        _empty("public_username"),
        CatalogItem.note.label("description"),
        BusinessProfile.direction.label("direction"),
        BusinessProfile.activity_type.label("activity_type"),
        (owner_profile.region.label("region") if owner_filtered else _empty("region")),
        (
            owner_profile.district.label("district")
            if owner_filtered
            else _empty("district")
        ),
        (
            owner_profile.mahalla.label("mahalla")
            if owner_filtered
            else _empty("mahalla")
        ),
        CatalogItem.image_object_key.label("image_object_key"),
        CatalogItem.price_text.label("price_text"),
        cast(CatalogItem.owner_state, String).label("owner_state"),
        case(
            (linked, CatalogItem.owner_name_snapshot),
            else_="Egasi hali akkauntini bog‘lamagan",
        ).label("owner_label"),
        case(
            (linked, CatalogItem.business_account_id),
            else_=None,
        ).label("owner_business_account_id"),
        case((linked, True), else_=False).label("can_order"),
        case((linked, True), else_=False).label("can_chat"),
        case(
            (map_available, CatalogItem.business_account_id),
            else_=None,
        ).label("map_business_account_id"),
        case(
            (map_available, BusinessProfile.name),
            else_=None,
        ).label("map_business_name"),
        case(
            (map_available, BusinessProfile.latitude),
            else_=None,
        ).label("map_latitude"),
        case(
            (map_available, BusinessProfile.longitude),
            else_=None,
        ).label("map_longitude"),
        literal(PublicResultKind.BUSINESS.value).label("map_owner_kind"),
    ).outerjoin(
        BusinessProfile,
        BusinessProfile.account_id == CatalogItem.business_account_id,
    )
    if owner_filtered:
        statement = statement.outerjoin(
            ProfileLink,
            ProfileLink.business_account_id == BusinessProfile.account_id,
        ).outerjoin(
            owner_profile,
            owner_profile.account_id == ProfileLink.user_account_id,
        )
    statement = statement.where(
        CatalogItem.status == "active",
        CatalogItem.review_state == ReviewState.READY,
        CatalogItem.kind == kind,
    )
    if params.q:
        statement = statement.where(
            or_(
                _contains(CatalogItem.name, params.q),
                _contains(CatalogItem.note, params.q),
                _contains(CatalogItem.price_text, params.q),
            )
        )
    for column, value in (
        (BusinessProfile.direction, params.direction),
        (BusinessProfile.activity_type, params.activity_type),
    ):
        if value:
            statement = statement.where(_contains(column, value))
    statement = statement.where(
        *_location_constraints(
            owner_profile.region,
            owner_profile.district,
            owner_profile.mahalla,
            params,
        )
    )
    return statement


def _listing_query(params: PublicSearchParams):
    owner_profile = aliased(UserProfile, name="listing_owner_profile")
    business_profile = aliased(BusinessProfile, name="listing_business_profile")
    profile_link = aliased(ProfileLink, name="listing_profile_link")
    linked_owner_id = func.coalesce(
        Listing.owner_user_account_id,
        profile_link.user_account_id,
    )
    map_visible = Listing.latitude.is_not(None) & Listing.longitude.is_not(None)
    first_photo_key = (
        select(ListingMedia.object_key)
        .where(
            ListingMedia.listing_id == Listing.id,
            ListingMedia.media_type == "photo",
        )
        .order_by(ListingMedia.position, ListingMedia.id)
        .limit(1)
        .correlate(Listing)
        .scalar_subquery()
    )
    statement = (
        select(
            literal(PublicResultKind.LISTING.value).label("kind"),
            Listing.id.label("account_id"),
            Listing.title.label("name"),
            _empty("public_username"),
            Listing.description.label("description"),
            func.coalesce(business_profile.direction, "").label("direction"),
            func.coalesce(business_profile.activity_type, "").label("activity_type"),
            func.coalesce(owner_profile.region, "").label("region"),
            func.coalesce(owner_profile.district, "").label("district"),
            func.coalesce(owner_profile.mahalla, "").label("mahalla"),
            func.coalesce(first_photo_key, "").label("image_object_key"),
            Listing.price_text.label("price_text"),
            literal("linked").cast(String).label("owner_state"),
            func.coalesce(business_profile.name, owner_profile.name, "").label(
                "owner_label"
            ),
            literal(None).cast(BigInteger).label("owner_business_account_id"),
            literal(False).cast(Boolean).label("can_order"),
            literal(False).cast(Boolean).label("can_chat"),
            case(
                (
                    map_visible,
                    func.coalesce(
                        Listing.owner_business_account_id,
                        Listing.owner_user_account_id,
                    ),
                ),
                else_=None,
            ).label("map_business_account_id"),
            case(
                (
                    map_visible,
                    func.coalesce(business_profile.name, owner_profile.name),
                ),
                else_=None,
            ).label("map_business_name"),
            case((map_visible, Listing.latitude), else_=None).label("map_latitude"),
            case((map_visible, Listing.longitude), else_=None).label("map_longitude"),
            case(
                (
                    Listing.owner_business_account_id.is_not(None),
                    PublicResultKind.BUSINESS.value,
                ),
                else_=PublicResultKind.USER.value,
            ).label("map_owner_kind"),
        )
        .outerjoin(
            business_profile,
            business_profile.account_id == Listing.owner_business_account_id,
        )
        .outerjoin(
            profile_link,
            profile_link.business_account_id == Listing.owner_business_account_id,
        )
        .outerjoin(owner_profile, owner_profile.account_id == linked_owner_id)
        .where(
            Listing.status == "active",
            Listing.visibility == "all",
            Listing.review_state == ReviewState.READY,
        )
    )
    if params.q:
        statement = statement.where(
            or_(
                _contains(Listing.title, params.q),
                _contains(Listing.description, params.q),
                _contains(Listing.address, params.q),
                _contains(Listing.price_text, params.q),
            )
        )
    for column, value in (
        (business_profile.direction, params.direction),
        (business_profile.activity_type, params.activity_type),
    ):
        if value:
            statement = statement.where(_contains(column, value))
    statement = statement.where(
        *_location_constraints(
            owner_profile.region,
            owner_profile.district,
            owner_profile.mahalla,
            params,
        )
    )
    return statement


def build_public_search_statements(
    params: PublicSearchParams,
    *,
    include_content: bool = True,
    include_listings: bool = False,
):
    queries = []
    if params.result_type in (
        PublicResultType.ALL,
        PublicResultType.USER,
    ):
        queries.append(_user_query(params))
    if params.result_type in (
        PublicResultType.ALL,
        PublicResultType.BUSINESS,
    ):
        queries.append(_business_query(params))
    if include_content and params.result_type in (
        PublicResultType.ALL,
        PublicResultType.PRODUCT,
    ):
        queries.append(_content_query(params, "product"))
    if include_content and params.result_type in (
        PublicResultType.ALL,
        PublicResultType.SERVICE,
    ):
        queries.append(_content_query(params, "service"))
    if include_listings and params.result_type in (
        PublicResultType.ALL,
        PublicResultType.LISTING,
    ):
        queries.append(_listing_query(params))

    if len(queries) == 1:
        combined = queries[0].subquery("public_profiles")
    else:
        combined = union_all(*queries).subquery("public_profiles")

    data_statement = (
        select(combined)
        .order_by(
            func.lower(combined.c.name),
            combined.c.kind,
            combined.c.account_id,
        )
        .limit(params.page_size)
        .offset(params.offset)
    )
    count_statement = select(func.count()).select_from(combined)
    return data_statement, count_statement
