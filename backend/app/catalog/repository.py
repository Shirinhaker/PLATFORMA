from collections.abc import Callable
import hashlib

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.model import CatalogItem
from app.catalog.schemas import (
    PublicCatalogItem,
    PublicCatalogParams,
    PublicCatalogResponse,
)
from app.legacy_migration.model import OwnerState, ReviewState
from app.profiles.model import BusinessProfile
from app.public_discovery.repository import build_public_id
from app.public_discovery.schemas import PublicResultKind


ImageUrlProvider = Callable[[str], str]


def build_content_public_id(kind: str, target_id: int) -> str:
    digest = hashlib.blake2s(
        f"{kind}:{target_id}".encode("utf-8"),
        digest_size=8,
        key=b"koprik-content-v1",
    ).hexdigest()
    prefix = "p" if kind == "product" else "s"
    return f"{prefix}_{digest}"


def _contains(column, value: str):
    return func.lower(column).contains(value.casefold())


def build_catalog_statements(params: PublicCatalogParams):
    base = (
        select(
            CatalogItem.id.label("target_id"),
            CatalogItem.kind,
            CatalogItem.name,
            CatalogItem.price_text,
            CatalogItem.unit,
            CatalogItem.note,
            CatalogItem.owner_state,
            CatalogItem.business_account_id,
            CatalogItem.owner_name_snapshot,
            CatalogItem.image_object_key,
            BusinessProfile.name.label("business_name"),
            BusinessProfile.direction,
            BusinessProfile.activity_type,
            BusinessProfile.address,
        )
        .outerjoin(
            BusinessProfile,
            BusinessProfile.account_id == CatalogItem.business_account_id,
        )
        .where(
            CatalogItem.status == "active",
            CatalogItem.review_state == ReviewState.READY,
        )
    )
    if params.kind:
        base = base.where(CatalogItem.kind == params.kind)
    if params.q:
        base = base.where(
            or_(
                _contains(CatalogItem.name, params.q),
                _contains(CatalogItem.note, params.q),
                _contains(CatalogItem.price_text, params.q),
                _contains(CatalogItem.owner_name_snapshot, params.q),
            )
        )
    for column, value in (
        (BusinessProfile.direction, params.direction),
        (BusinessProfile.activity_type, params.activity_type),
        (BusinessProfile.address, params.region),
        (BusinessProfile.address, params.district),
        (BusinessProfile.address, params.mahalla),
    ):
        if value:
            base = base.where(_contains(column, value))

    projected = base.subquery("public_catalog")
    data = (
        select(projected)
        .order_by(
            func.lower(projected.c.name),
            projected.c.kind,
            projected.c.target_id,
        )
        .limit(params.page_size)
        .offset(params.offset)
    )
    count = select(func.count()).select_from(projected)
    return data, count


async def list_public_catalog(
    session: AsyncSession,
    params: PublicCatalogParams,
    image_url_provider: ImageUrlProvider,
) -> PublicCatalogResponse:
    data, count = build_catalog_statements(params)
    rows = (await session.execute(data)).mappings().all()
    total = int((await session.execute(count)).scalar_one())
    return PublicCatalogResponse(
        items=[
            _public_item(row, image_url_provider)
            for row in rows
        ],
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


async def get_public_catalog(
    session: AsyncSession,
    public_id: str,
    image_url_provider: ImageUrlProvider,
) -> PublicCatalogItem | None:
    data, _ = build_catalog_statements(
        PublicCatalogParams(page=1, page_size=50)
    )
    statement = data.limit(None).offset(None)
    rows = (await session.execute(statement)).mappings()
    for row in rows:
        if (
            build_content_public_id(row["kind"], row["target_id"])
            == public_id
        ):
            return _public_item(row, image_url_provider)
    return None


def _public_item(row, image_url_provider: ImageUrlProvider):
    linked = (
        row["owner_state"] == OwnerState.LINKED
        or row["owner_state"] == OwnerState.LINKED.value
    ) and row["business_account_id"] is not None
    owner_name = row["business_name"] or row["owner_name_snapshot"] or ""
    owner_public_id = (
        build_public_id(
            PublicResultKind.BUSINESS,
            int(row["business_account_id"]),
        )
        if linked
        else ""
    )
    return PublicCatalogItem(
        kind=row["kind"],
        public_id=build_content_public_id(row["kind"], row["target_id"]),
        name=row["name"],
        price_text=row["price_text"],
        unit=row["unit"] or "dona",
        note=row["note"],
        owner_state="linked" if linked else "unlinked",
        owner_public_id=owner_public_id,
        owner_name=owner_name,
        owner_label=(
            owner_name
            if linked
            else "Egasi hali akkauntini bog‘lamagan"
        ),
        direction=row["direction"] or "",
        activity_type=row["activity_type"] or "",
        region="",
        district=row["address"] or "",
        mahalla="",
        image_url=image_url_provider(row["image_object_key"]),
        can_order=linked,
        can_chat=linked,
    )
