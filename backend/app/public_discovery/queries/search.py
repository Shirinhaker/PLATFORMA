"""Qidiruv natijalarini yig'ish."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.public_discovery.queries.constants import (
    ImageUrlProvider,
)
from app.public_discovery.queries.helpers import (
    build_listing_public_id,
    build_public_id,
)
from app.public_discovery.queries.statements import (
    build_public_search_statements,
)
from app.public_discovery.schemas import (
    PublicResultKind,
    PublicSearchItem,
    PublicSearchMapPoint,
    PublicSearchParams,
    PublicSearchResponse,
)


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
