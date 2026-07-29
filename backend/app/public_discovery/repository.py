import hashlib

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

from app.accounts.model import Account
from app.catalog.model import CatalogItem
from app.legacy_migration.model import ReviewState
from app.profiles.model import BusinessProfile, UserProfile
from app.public_discovery.schemas import (
    PublicResultKind,
    PublicResultType,
    PublicSearchItem,
    PublicSearchParams,
    PublicSearchResponse,
)


def build_public_id(kind: PublicResultKind, account_id: int) -> str:
    digest = hashlib.blake2s(
        f"{kind.value}:{account_id}".encode("utf-8"),
        digest_size=8,
        person=b"koprik",
    ).hexdigest()
    prefix = "u" if kind is PublicResultKind.USER else "b"
    return f"{prefix}_{digest}"


def _empty(label: str):
    return literal("").cast(String).label(label)


def _contains(column, value: str):
    return func.lower(column).contains(value.casefold())


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
    for column, value in (
        (UserProfile.region, params.region),
        (UserProfile.district, params.district),
        (UserProfile.mahalla, params.mahalla),
    ):
        if value:
            statement = statement.where(_contains(column, value))
    return statement


def _business_query(params: PublicSearchParams):
    statement = (
        select(
            literal(PublicResultKind.BUSINESS.value).label("kind"),
            Account.id.label("account_id"),
            BusinessProfile.name.label("name"),
            BusinessProfile.public_username.label("public_username"),
            BusinessProfile.description.label("description"),
            BusinessProfile.direction.label("direction"),
            BusinessProfile.activity_type.label("activity_type"),
            _empty("region"),
            _empty("district"),
            _empty("mahalla"),
            _empty("image_url"),
            literal(None).cast(String).label("price_text"),
            literal(None).cast(String).label("owner_state"),
            literal(None).cast(String).label("owner_label"),
            literal(None).cast(Boolean).label("can_order"),
            literal(None).cast(Boolean).label("can_chat"),
        )
        .join(BusinessProfile, BusinessProfile.account_id == Account.id)
        .where(Account.status == "active")
    )

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

    for value in (params.region, params.district, params.mahalla):
        if value:
            statement = statement.where(
                _contains(BusinessProfile.address, value)
            )
    return statement


def _content_query(params: PublicSearchParams, kind: str):
    linked = (
        (CatalogItem.owner_state == "linked")
        & CatalogItem.business_account_id.is_not(None)
    )
    statement = (
        select(
            literal(kind).label("kind"),
            CatalogItem.id.label("account_id"),
            CatalogItem.name.label("name"),
            _empty("public_username"),
            CatalogItem.note.label("description"),
            _empty("direction"),
            _empty("activity_type"),
            _empty("region"),
            _empty("district"),
            _empty("mahalla"),
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
        .where(
            CatalogItem.status == "active",
            CatalogItem.review_state == ReviewState.READY,
            CatalogItem.kind == kind,
        )
    )
    if params.q:
        statement = statement.where(
            or_(
                _contains(CatalogItem.name, params.q),
                _contains(CatalogItem.note, params.q),
                _contains(CatalogItem.price_text, params.q),
            )
        )
    if any(
        (
            params.direction,
            params.activity_type,
            params.region,
            params.district,
            params.mahalla,
        )
    ):
        statement = statement.where(literal(False))
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
