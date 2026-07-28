import hashlib

from sqlalchemy import (
    String,
    func,
    literal,
    or_,
    select,
    union_all,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account
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


def build_public_search_statements(params: PublicSearchParams):
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
) -> PublicSearchResponse:
    data_statement, count_statement = build_public_search_statements(params)
    rows = (await session.execute(data_statement)).mappings().all()
    total = int((await session.execute(count_statement)).scalar_one())

    items = [
        PublicSearchItem(
            kind=row["kind"],
            public_id=build_public_id(
                PublicResultKind(row["kind"]),
                row["account_id"],
            ),
            name=row["name"],
            public_username=row["public_username"],
            description=row["description"],
            direction=row["direction"],
            activity_type=row["activity_type"],
            region=row["region"],
            district=row["district"],
            mahalla=row["mahalla"],
            image_url=row["image_url"],
        )
        for row in rows
    ]
    return PublicSearchResponse(
        items=items,
        page=params.page,
        page_size=params.page_size,
        total=total,
    )
