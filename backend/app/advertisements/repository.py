import hashlib
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, time

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.advertisements.model import Advertisement
from app.advertisements.schemas import PublicAdvertisement
from app.legacy_migration.model import ReviewState
from app.public_discovery.repository import build_public_id
from app.public_discovery.schemas import PublicResultKind


ImageUrlProvider = Callable[[str], str]


def build_advertisement_public_id(target_id: int) -> str:
    digest = hashlib.blake2s(
        f"advertisement:{target_id}".encode(),
        digest_size=8,
        key=b"koprik-ad-v1",
    ).hexdigest()
    return f"a_{digest}"


def daily_window_active(
    current: time,
    all_day: bool,
    start: time | None,
    end: time | None,
) -> bool:
    if all_day:
        return True
    if start is None or end is None or start == end:
        return False
    if start < end:
        return start <= current < end
    return current >= start or current < end


def target_specificity(
    targets: list[dict[str, str]],
    region: str,
    district: str,
) -> int | None:
    if not targets:
        return 0
    region_key = region.casefold()
    district_key = district.casefold()
    scores = []
    for target in targets:
        target_region = str(target.get("region") or "").casefold()
        target_district = str(target.get("district") or "").casefold()
        if target_region and target_region != region_key:
            continue
        if target_district and target_district != district_key:
            continue
        scores.append(2 if target_district else 1 if target_region else 0)
    return max(scores) if scores else None


async def select_active_advertisements(
    session: AsyncSession,
    *,
    now: datetime,
    placement: str,
    region: str,
    district: str,
    image_url_provider: ImageUrlProvider,
) -> list[PublicAdvertisement]:
    statement = (
        select(Advertisement)
        .where(
            Advertisement.status == "active",
            Advertisement.review_state == ReviewState.READY,
            Advertisement.placement == placement,
            Advertisement.start_at <= now,
            Advertisement.end_at > now,
        )
        .order_by(Advertisement.start_at, Advertisement.id)
    )
    candidates = (await session.scalars(statement)).all()
    ranked = []
    current_time = now.time().replace(tzinfo=None)
    for candidate in candidates:
        if not daily_window_active(
            current_time,
            candidate.daily_all_day,
            candidate.daily_start,
            candidate.daily_end,
        ):
            continue
        specificity = target_specificity(
            candidate.targets_json,
            region,
            district,
        )
        if specificity is None:
            continue
        ranked.append((specificity, candidate))
    ranked.sort(
        key=lambda value: (
            -value[0],
            value[1].start_at,
            value[1].id,
        )
    )
    return [
        _public_advertisement(candidate, image_url_provider)
        for _, candidate in ranked
    ]


def _public_advertisement(
    advertisement: Advertisement,
    image_url_provider: ImageUrlProvider,
) -> PublicAdvertisement:
    owner_id = None
    owner_kind = None
    if advertisement.owner_business_account_id is not None:
        owner_id = advertisement.owner_business_account_id
        owner_kind = PublicResultKind.BUSINESS
    elif advertisement.owner_user_account_id is not None:
        owner_id = advertisement.owner_user_account_id
        owner_kind = PublicResultKind.USER
    return PublicAdvertisement(
        public_id=build_advertisement_public_id(advertisement.id),
        title=advertisement.title,
        caption=advertisement.caption,
        owner_public_id=(
            build_public_id(owner_kind, owner_id)
            if owner_id is not None and owner_kind is not None
            else ""
        ),
        owner_kind=owner_kind.value if owner_kind is not None else None,
        desktop_image_url=image_url_provider(
            advertisement.desktop_image_object_key
        ),
        mobile_image_url=image_url_provider(
            advertisement.mobile_image_object_key
        ),
        crop_x=advertisement.crop_x,
        crop_y=advertisement.crop_y,
        crop_zoom=advertisement.crop_zoom,
    )


class AdvertisementService:
    def __init__(
        self,
        session_factory: Callable[
            [], AbstractAsyncContextManager[AsyncSession]
        ],
        image_url_provider: ImageUrlProvider,
    ) -> None:
        self._session_factory = session_factory
        self._image_url_provider = image_url_provider

    async def list_public(self, **filters) -> list[PublicAdvertisement]:
        async with self._session_factory() as session:
            result = await select_active_advertisements(
                session,
                image_url_provider=self._image_url_provider,
                **filters,
            )
            await session.rollback()
            return result

    async def record_public_views(self, public_ids: list[str]) -> None:
        await self._increment_public_metric(
            public_ids,
            metric="views",
        )

    async def record_public_click(self, public_id: str) -> None:
        await self._increment_public_metric(
            [public_id],
            metric="clicks",
        )

    async def _increment_public_metric(
        self,
        public_ids: list[str],
        *,
        metric: str,
    ) -> None:
        requested = set(public_ids[:5])
        if not requested:
            return
        async with self._session_factory() as session:
            now = datetime.now(UTC)
            internal_ids = list(
                (
                    await session.scalars(
                        select(Advertisement.id).where(
                            Advertisement.status == "active",
                            Advertisement.review_state == ReviewState.READY,
                            Advertisement.start_at <= now,
                            Advertisement.end_at > now,
                        )
                    )
                ).all()
            )
            matched = [
                target_id
                for target_id in internal_ids
                if build_advertisement_public_id(target_id) in requested
            ]
            if matched:
                column = (
                    Advertisement.views
                    if metric == "views"
                    else Advertisement.clicks
                )
                await session.execute(
                    update(Advertisement)
                    .where(Advertisement.id.in_(matched))
                    .values({metric: column + 1})
                )
                await session.commit()
            else:
                await session.rollback()
