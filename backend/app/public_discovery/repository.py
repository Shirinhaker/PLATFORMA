from collections.abc import Callable
import hashlib
import time

from sqlalchemy import (
    Boolean,
    String,
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

from app.accounts.model import Account
from app.cabinet_records.repository import CabinetRecordRepository
from app.catalog.model import CatalogItem
from app.legacy_migration.model import LegacyIdMap, ReviewState
from app.listings.model import Listing, ListingMedia
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile
from app.public_discovery.schemas import (
    PublicDistrictOffer,
    PublicDistrictOffersResponse,
    PublicHomeBusinessPin,
    PublicHomeMapResponse,
    PublicHomeSpecialistPin,
    PublicFollowedProfile,
    PublicResultKind,
    PublicResultType,
    PublicSearchItem,
    PublicSearchParams,
    PublicSearchResponse,
)


ImageUrlProvider = Callable[[str], str]
_cabinet_records = CabinetRecordRepository()


def build_public_id(kind: PublicResultKind, account_id: int) -> str:
    digest = hashlib.blake2s(
        f"{kind.value}:{account_id}".encode("utf-8"),
        digest_size=8,
        person=b"koprik",
    ).hexdigest()
    prefix = "u" if kind is PublicResultKind.USER else "b"
    return f"{prefix}_{digest}"


def build_listing_public_id(listing_id: int) -> str:
    digest = hashlib.blake2s(
        f"listing:{listing_id}".encode("utf-8"),
        digest_size=8,
        key=b"koprik-content-v1",
    ).hexdigest()
    return f"l_{digest}"


def _empty(label: str):
    return literal("").cast(String).label(label)


def _contains(column, value: str):
    return func.lower(column).contains(value.casefold())


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
            _empty("description"),
            _empty("direction"),
            _empty("activity_type"),
            UserProfile.region.label("region"),
            UserProfile.district.label("district"),
            UserProfile.mahalla.label("mahalla"),
            _empty("image_url"),
            literal(None).cast(String).label("price_text"),
            literal(None).cast(String).label("owner_state"),
            literal(None).cast(String).label("owner_label"),
            literal(None).cast(Boolean).label("can_order"),
            literal(None).cast(Boolean).label("can_chat"),
        )
        .join(UserProfile, UserProfile.account_id == Account.id)
        .where(Account.status == "active")
    )

    if params.q:
        statement = statement.where(
            or_(
                _contains(UserProfile.name, params.q),
                _contains(UserProfile.public_username, params.q),
            )
        )
    statement = statement.where(*_location_constraints(
        UserProfile.region,
        UserProfile.district,
        UserProfile.mahalla,
        params,
    ))
    return statement


def _business_query(params: PublicSearchParams):
    owner_profile = aliased(UserProfile, name="business_owner_profile")
    location_filtered = bool(
        params.region or params.district or params.mahalla
    )
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
        _empty("image_url"),
        literal(None).cast(String).label("price_text"),
        literal(None).cast(String).label("owner_state"),
        literal(None).cast(String).label("owner_label"),
        literal(None).cast(Boolean).label("can_order"),
        literal(None).cast(Boolean).label("can_chat"),
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

    statement = statement.where(*_location_constraints(
        owner_profile.region,
        owner_profile.district,
        owner_profile.mahalla,
        params,
    ))
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
        (CatalogItem.owner_state == "linked")
        & CatalogItem.business_account_id.is_not(None)
    )
    statement = select(
        literal(kind).label("kind"),
        CatalogItem.id.label("account_id"),
        CatalogItem.name.label("name"),
        _empty("public_username"),
        CatalogItem.note.label("description"),
        (
            BusinessProfile.direction.label("direction")
            if owner_filtered
            else _empty("direction")
        ),
        (
            BusinessProfile.activity_type.label("activity_type")
            if owner_filtered
            else _empty("activity_type")
        ),
        (
            owner_profile.region.label("region")
            if owner_filtered
            else _empty("region")
        ),
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
        _empty("image_url"),
        CatalogItem.price_text.label("price_text"),
        cast(CatalogItem.owner_state, String).label("owner_state"),
        case(
            (linked, CatalogItem.owner_name_snapshot),
            else_="Egasi hali akkauntini bog‘lamagan",
        ).label("owner_label"),
        case((linked, True), else_=False).label("can_order"),
        case((linked, True), else_=False).label("can_chat"),
    )
    if owner_filtered:
        statement = statement.outerjoin(
            BusinessProfile,
            BusinessProfile.account_id == CatalogItem.business_account_id,
        ).outerjoin(
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
    statement = statement.where(*_location_constraints(
        owner_profile.region,
        owner_profile.district,
        owner_profile.mahalla,
        params,
    ))
    return statement


def build_public_search_statements(
    params: PublicSearchParams,
    *,
    include_content: bool = True,
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
) -> PublicSearchResponse:
    data_statement, count_statement = build_public_search_statements(
        params,
        include_content=include_content,
    )
    rows = (await session.execute(data_statement)).mappings().all()
    total = int((await session.execute(count_statement)).scalar_one())

    items = []
    for row in rows:
        kind = PublicResultKind(row["kind"])
        if kind in (PublicResultKind.PRODUCT, PublicResultKind.SERVICE):
            from app.catalog.repository import build_content_public_id

            public_id = build_content_public_id(kind.value, row["account_id"])
        else:
            public_id = build_public_id(kind, row["account_id"])
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
                image_url=row["image_url"],
                price_text=row["price_text"],
                owner_state=row["owner_state"],
                owner_label=row["owner_label"],
                can_order=row["can_order"],
                can_chat=row["can_chat"],
            )
        )
    return PublicSearchResponse(
        items=items,
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


def _has_active_pro_subscription(profile: BusinessProfile) -> bool:
    payload = (
        profile.cabinet_payload
        if isinstance(profile.cabinet_payload, dict)
        else {}
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
            and str(row.get("plan_code") or "") == "pro"
            and expires_at > now
        ):
            return True
    return False


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
            BusinessProfile.map_visible.is_(True),
            BusinessProfile.latitude.is_not(None),
            BusinessProfile.longitude.is_not(None),
            _contains(business_owner.district, district),
        )
        .order_by(func.lower(BusinessProfile.name), BusinessProfile.account_id)
    )
    user_statement = (
        select(UserProfile)
        .join(Account, Account.id == UserProfile.account_id)
        .where(
            Account.status == "active",
            UserProfile.latitude.is_not(None),
            UserProfile.longitude.is_not(None),
            _contains(UserProfile.district, district),
        )
        .order_by(func.lower(UserProfile.name), UserProfile.account_id)
    )
    business_profiles = list(
        (await session.scalars(business_statement)).all()
    )
    user_profiles = list((await session.scalars(user_statement)).all())

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
    followed_users = {
        item.public_id for item in followed if item.kind == "user"
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
        ) in followed_businesses
        or _has_active_pro_subscription(profile)
    ]
    specialists = []
    for profile in user_profiles:
        specialist = (
            profile.specialist_profile
            if isinstance(profile.specialist_profile, dict)
            else {}
        )
        if not specialist:
            continue
        public_id = build_public_id(
            PublicResultKind.USER,
            profile.account_id,
        )
        if not bool(specialist.get("visible")) or public_id not in followed_users:
            continue
        specialists.append(
            PublicHomeSpecialistPin(
                user_id=profile.account_id,
                public_id=public_id,
                name=profile.name or "Foydalanuvchi",
                kasb=str(
                    specialist.get("profession")
                    or specialist.get("kasb")
                    or "Mutaxasis"
                ),
                is_gov=bool(specialist.get("is_gov")),
                lat=profile.latitude,
                lng=profile.longitude,
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
            _contains(business_owner.district, district),
        )
        .order_by(CatalogItem.id)
    )
    catalog_rows = [
        row
        for row in (await session.execute(statement)).all()
        if _has_active_pro_subscription(row[1])
    ]
    grouped: dict[
        int,
        tuple[
            BusinessProfile,
            list[tuple[str, CatalogItem | Listing]],
        ],
    ] = {}
    for catalog_item, business in catalog_rows:
        grouped.setdefault(business.account_id, (business, []))[1].append(
            (catalog_item.kind, catalog_item)
        )

    if include_listings:
        listing_statement = (
            select(Listing, BusinessProfile)
            .join(
                BusinessProfile,
                BusinessProfile.account_id
                == Listing.owner_business_account_id,
            )
            .join(Account, Account.id == BusinessProfile.account_id)
            .join(
                ProfileLink,
                ProfileLink.business_account_id
                == BusinessProfile.account_id,
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
                _contains(business_owner.district, district),
            )
            .order_by(Listing.id)
        )
        listing_rows = [
            row
            for row in (await session.execute(listing_statement)).all()
            if _has_active_pro_subscription(row[1])
        ]
        for listing, business in listing_rows:
            grouped.setdefault(
                business.account_id,
                (business, []),
            )[1].append(("listing", listing))
    business_ids = sorted(grouped)
    if business_ids:
        seed = hashlib.sha256(district.casefold().encode("utf-8")).digest()
        offset = (int.from_bytes(seed[:8], "big") + slot) % len(business_ids)
        business_ids = (business_ids[offset:] + business_ids[:offset])[:20]

    selected: list[
        tuple[str, CatalogItem | Listing, BusinessProfile]
    ] = []
    for business_id in business_ids:
        business, content_items = grouped[business_id]
        kinds = sorted({kind for kind, _ in content_items})
        selected_kind = kinds[(slot + business_id) % len(kinds)]
        candidates = [
            item for kind, item in content_items if kind == selected_kind
        ]
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
    if account_type == "business":
        profile = await session.get(BusinessProfile, account_id)
        resource = "following"
    else:
        profile = await session.get(UserProfile, account_id)
        resource = "follows"
    if profile is None:
        return []

    rows = await _cabinet_records.read_resource(
        session,
        account_id=account_id,
        account_type=account_type,
        resource=resource,
    )
    if not rows:
        payload = (
            profile.cabinet_payload
            if isinstance(profile.cabinet_payload, dict)
            else {}
        )
        fallback = payload.get(resource, [])
        rows = fallback if isinstance(fallback, list) else []

    targets: list[tuple[str, int]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = "business" if row.get("target_kind") == "business" else "user"
        try:
            legacy_id = int(row.get("target_id") or 0)
        except (TypeError, ValueError):
            continue
        if legacy_id > 0:
            targets.append((kind, legacy_id))
    if not targets:
        return []

    mapping_rows = list(
        (
            await session.scalars(
                select(LegacyIdMap).where(
                    or_(
                        *[
                            (
                                LegacyIdMap.entity_type
                                == f"{kind}_account"
                            )
                            & (LegacyIdMap.legacy_id == legacy_id)
                            for kind, legacy_id in targets
                        ]
                    ),
                    LegacyIdMap.target_id.is_not(None),
                )
            )
        ).all()
    )
    target_ids = {
        (mapping.entity_type.removesuffix("_account"), mapping.legacy_id):
        mapping.target_id
        for mapping in mapping_rows
    }
    result: list[PublicFollowedProfile] = []
    for kind, legacy_id in targets:
        target_id = target_ids.get((kind, legacy_id))
        if target_id is None:
            continue
        if kind == "business":
            target = await session.get(BusinessProfile, target_id)
            if target is None:
                continue
            result.append(
                PublicFollowedProfile(
                    kind="business",
                    public_id=build_public_id(
                        PublicResultKind.BUSINESS,
                        target_id,
                    ),
                    name=target.name,
                    image_url=image_url_provider(target.logo_object_key),
                    crop_x=target.logo_x,
                    crop_y=target.logo_y,
                    crop_zoom=target.logo_zoom,
                )
            )
        else:
            target = await session.get(UserProfile, target_id)
            if target is None:
                continue
            result.append(
                PublicFollowedProfile(
                    kind="user",
                    public_id=build_public_id(
                        PublicResultKind.USER,
                        target_id,
                    ),
                    name=target.name,
                    image_url=image_url_provider(target.avatar_object_key),
                    crop_x=target.avatar_x,
                    crop_y=target.avatar_y,
                    crop_zoom=target.avatar_zoom,
                )
            )
    return result
