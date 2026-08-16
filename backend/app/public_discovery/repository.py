import hashlib
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone

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
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.accounts.model import Account, AccountType
from app.cabinet_records.repository import CabinetRecordRepository
from app.catalog.model import CatalogGroup, CatalogItem
from app.follows.model import ProfileFollow
from app.legacy_migration.model import ReviewState
from app.listings.model import Listing, ListingMedia
from app.payments.model import BusinessSubscription
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile
from app.public_discovery.schemas import (
    PublicDistrictOffer,
    PublicDistrictOffersResponse,
    PublicFollowedProfile,
    PublicHomeBusinessPin,
    PublicHomeMapResponse,
    PublicHomeSpecialistPin,
    PublicProfileDetail,
    PublicProfileItem,
    PublicProfileListing,
    PublicResultKind,
    PublicResultType,
    PublicSearchItem,
    PublicSearchMapPoint,
    PublicSearchParams,
    PublicSearchResponse,
    PublicSpecialistCredential,
    PublicSpecialistOffer,
    PublicSpecialistPortfolio,
    PublicSpecialistSummary,
)
from app.public_ids import (
    build_listing_public_id as _build_listing_public_id,
)
from app.public_ids import (
    build_profile_public_id,
)
from app.queues.repository import active_provider_count, active_queue_count
from app.queues.service import QUEUE_DIRECTIONS
from app.specialists.model import (
    SpecialistCredential,
    SpecialistOffer,
    SpecialistPortfolio,
    SpecialistProfile,
)

ImageUrlProvider = Callable[[str], str]
_cabinet_records = CabinetRecordRepository()
UZBEKISTAN_TZ = timezone(timedelta(hours=5))


def _bounded_integer(value: object, maximum: int) -> int:
    try:
        return max(0, min(maximum, int(value or 0)))
    except (TypeError, ValueError):
        return 0


def build_public_id(kind: PublicResultKind, account_id: int) -> str:
    return build_profile_public_id(kind.value, account_id)


def build_listing_public_id(listing_id: int) -> str:
    return _build_listing_public_id(listing_id)


def _empty(label: str):
    return literal("").cast(String).label(label)


def _contains(column, value: str):
    return func.lower(column).contains(value.casefold())


_LOCATION_APOSTROPHES = ("‘", "’", "ʻ", "ʼ", "`", "´", "ʹ")
_LOCATION_SUFFIXES = (" viloyati", " tumani", " shahri")


def _location_key(value: str) -> str:
    key = " ".join(str(value or "").casefold().strip().split())
    for apostrophe in _LOCATION_APOSTROPHES:
        key = key.replace(apostrophe, "'")
    for suffix in _LOCATION_SUFFIXES:
        if key.endswith(suffix):
            key = key[: -len(suffix)].rstrip()
            break
    return key


def _location_contains(column, value: str):
    """Eski va yangi o'zbekcha apostrof yozuvlarini SQLda birga qidiradi."""
    key = _location_key(value)
    variants = {key}
    variants.update(
        key.replace("'", apostrophe) for apostrophe in _LOCATION_APOSTROPHES
    )
    return or_(
        *(
            func.lower(column).contains(variant)
            for variant in sorted(variants)
            if variant
        )
    )


def _location_constraints(
    region_column,
    district_column,
    mahalla_column,
    params: PublicSearchParams,
):
    constraints = []
    if params.region:
        region_match = _contains(region_column, params.region)
        if params.district:
            # V7 ko'chirishda ayrim eski profillarning tumani saqlangan,
            # ammo viloyati bo'sh qolgan. Tuman qat'iy mos bo'lsa, shu yozuvni
            # qidiruvdan yo'qotmaymiz; region mavjud yozuvlarda baribir tekshiriladi.
            region_match = or_(
                func.coalesce(func.trim(region_column), "") == "",
                region_match,
            )
        constraints.append(region_match)
    if params.district:
        constraints.append(_contains(district_column, params.district))
    if params.mahalla:
        constraints.append(_contains(mahalla_column, params.mahalla))
    return constraints


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


async def search_public_profiles(
    session: AsyncSession,
    params: PublicSearchParams,
    *,
    include_content: bool = True,
    include_listings: bool = False,
    image_url_provider: ImageUrlProvider | None = None,
) -> PublicSearchResponse:
    data_statement, count_statement = build_public_search_statements(
        params,
        include_content=include_content,
        include_listings=include_listings,
    )
    rows = (await session.execute(data_statement)).mappings().all()
    total = int((await session.execute(count_statement)).scalar_one())

    resolve_image = image_url_provider or (
        lambda object_key: f"/media/{object_key}" if object_key else ""
    )
    items = []
    for row in rows:
        kind = PublicResultKind(row["kind"])
        if kind in (PublicResultKind.PRODUCT, PublicResultKind.SERVICE):
            from app.catalog.repository import build_content_public_id

            public_id = build_content_public_id(kind.value, row["account_id"])
        elif kind is PublicResultKind.LISTING:
            public_id = build_listing_public_id(int(row["account_id"]))
        else:
            public_id = build_public_id(kind, row["account_id"])
        map_point = None
        if row["map_business_account_id"] is not None:
            map_owner_kind = PublicResultKind(
                row["map_owner_kind"] or PublicResultKind.BUSINESS.value
            )
            map_point = PublicSearchMapPoint(
                business_public_id=build_public_id(
                    map_owner_kind,
                    int(row["map_business_account_id"]),
                ),
                business_name=row["map_business_name"],
                latitude=row["map_latitude"],
                longitude=row["map_longitude"],
            )
        items.append(
            PublicSearchItem(
                kind=row["kind"],
                public_id=public_id,
                name=row["name"],
                public_username=row["public_username"],
                description=row["description"],
                direction=row["direction"],
                activity_type=row["activity_type"],
                region=row["region"],
                district=row["district"],
                mahalla=row["mahalla"],
                image_url=resolve_image(row["image_object_key"] or ""),
                price_text=row["price_text"],
                owner_state=row["owner_state"],
                owner_label=row["owner_label"],
                owner_public_id=(
                    build_public_id(
                        PublicResultKind.BUSINESS,
                        int(row["owner_business_account_id"]),
                    )
                    if row["owner_business_account_id"] is not None
                    else None
                ),
                can_order=row["can_order"],
                can_chat=row["can_chat"],
                map_point=map_point,
            )
        )
    return PublicSearchResponse(
        items=items,
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


def _has_legacy_active_subscription(
    profile: BusinessProfile,
    eligible_plan_codes: frozenset[str],
) -> bool:
    payload = (
        profile.cabinet_payload if isinstance(profile.cabinet_payload, dict) else {}
    )
    rows = payload.get("business_subscriptions", [])
    if not isinstance(rows, list):
        return False
    now = int(time.time())
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            expires_at = int(row.get("expires_at") or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if (
            str(row.get("status") or "") == "active"
            and str(row.get("plan_code") or "") in eligible_plan_codes
            and expires_at > now
        ):
            return True
    return False


async def _active_subscription_business_ids(
    session: AsyncSession,
    account_ids: set[int],
    eligible_plan_codes: frozenset[str],
) -> set[int]:
    """Faol Plus/Pro bizneslarni yangi jadvaldan bir so'rovda oladi."""
    if not account_ids or not eligible_plan_codes:
        return set()
    rows = await session.scalars(
        select(BusinessSubscription.business_account_id)
        .where(
            BusinessSubscription.business_account_id.in_(account_ids),
            BusinessSubscription.plan_code.in_(sorted(eligible_plan_codes)),
            BusinessSubscription.status == "active",
            BusinessSubscription.expires_at > int(time.time()),
        )
        .distinct()
    )
    return {int(account_id) for account_id in rows.all()}


async def _active_pro_business_ids(
    session: AsyncSession,
    account_ids: set[int],
) -> set[int]:
    """Xarita v1656 qoidasi: faol Pro bizneslar."""
    return await _active_subscription_business_ids(
        session,
        account_ids,
        frozenset({"pro"}),
    )


async def _active_home_offer_business_ids(
    session: AsyncSession,
    account_ids: set[int],
) -> set[int]:
    """Tuman kartalari v1656 qoidasi: Plus va Pro teng huquqli."""
    return await _active_subscription_business_ids(
        session,
        account_ids,
        frozenset({"plus", "pro"}),
    )


def _has_active_subscription(
    profile: BusinessProfile,
    active_business_ids: set[int],
    eligible_plan_codes: frozenset[str],
) -> bool:
    return profile.account_id in active_business_ids or _has_legacy_active_subscription(
        profile, eligible_plan_codes
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
