from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import AccountType
from app.catalog.cache_epoch import CatalogCacheEpoch
from app.core.errors import ApiError
from app.legacy_migration.model import ReviewState
from app.listings.model import Listing
from app.listings.repository import ListingRepository
from app.listings.schemas import (
    ListingCreate,
    ListingMediaAttachment,
    ListingMediaRead,
    ListingPatch,
    ListingRead,
)
from app.public_discovery.repository import build_listing_public_id, build_public_id
from app.public_discovery.schemas import PublicResultKind


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
ImageUrlProvider = Callable[[str], str]
PUBLIC_ID_RE = re.compile(r"^l_[0-9a-f]{16}$")
CATEGORIES = {"uy", "ish", "moshina", "hayvon", "texnika", "boshqa"}


class ListingService:
    def __init__(
        self,
        session_factory: SessionFactory,
        image_url_provider: ImageUrlProvider,
        *,
        repository: ListingRepository | None = None,
        cache_epoch: CatalogCacheEpoch | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._image_url_provider = image_url_provider
        self._repository = repository or ListingRepository()
        self._cache_epoch = cache_epoch

    async def counts(self) -> dict[str, int]:
        async with self._session_factory() as session:
            value = await self._repository.counts(session)
            response = {
                category: value.get(category, 0) for category in CATEGORIES
            }
            await session.rollback()
            return response

    async def list_public(
        self,
        *,
        category: str,
        query: str,
        current_account_id: int | None = None,
        current_account_type: AccountType | None = None,
    ) -> list[ListingRead]:
        async with self._session_factory() as session:
            rows = await self._repository.list_public(
                session,
                category=category if category in CATEGORIES else "",
                query=query.strip(),
            )
            result = await self._project(
                session,
                rows,
                current_account_id=await self._save_owner_account_id(
                    session,
                    current_account_id,
                    current_account_type,
                ),
            )
            await session.rollback()
            return result

    async def get_public(
        self,
        public_id: str,
        *,
        current_account_id: int | None = None,
        current_account_type: AccountType | None = None,
    ) -> ListingRead | None:
        async with self._session_factory() as session:
            listing = await self._resolve(session, public_id)
            if (
                listing is None
                or listing.status != "active"
                or listing.review_state is not ReviewState.READY
            ):
                await session.rollback()
                return None
            projected = await self._project(
                session,
                [listing],
                current_account_id=await self._save_owner_account_id(
                    session,
                    current_account_id,
                    current_account_type,
                ),
            )
            await session.rollback()
            return projected[0]

    async def list_owner(
        self,
        *,
        account_id: int,
        account_type: AccountType,
    ) -> list[ListingRead]:
        async with self._session_factory() as session:
            rows = await self._repository.list_owner(
                session,
                account_id=account_id,
                account_type=account_type.value,
            )
            result = await self._project(session, rows, current_account_id=account_id)
            await session.rollback()
            return result

    async def create(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: ListingCreate,
    ) -> ListingRead:
        async with self._session_factory() as session:
            now = datetime.now(UTC)
            listing = Listing(
                owner_user_account_id=(
                    account_id if account_type is AccountType.USER else None
                ),
                owner_business_account_id=(
                    account_id if account_type is AccountType.BUSINESS else None
                ),
                source_record_key=None,
                category=body.cat,
                title=body.title,
                price_text=body.price,
                description=body.descr,
                address=body.address,
                latitude=body.lat,
                longitude=body.lng,
                visibility=(
                    body.visibility if account_type is AccountType.BUSINESS else "all"
                ),
                status="active",
                review_state=ReviewState.READY,
                migration_run_id=None,
                created_at=now,
                updated_at=now,
            )
            session.add(listing)
            await session.flush()
            await self._repository.replace_media(
                session,
                listing_id=listing.id,
                media=self._validated_media(body.media, account_id, account_type),
            )
            await session.flush()
            await session.commit()
            await self._bump()
            return (await self._project(
                session,
                [listing],
                current_account_id=account_id,
            ))[0]

    async def patch(
        self,
        *,
        public_id: str,
        account_id: int,
        account_type: AccountType,
        body: ListingPatch,
    ) -> ListingRead:
        async with self._session_factory() as session:
            listing = await self._owned(session, public_id, account_id, account_type)
            changes = body.model_dump(exclude_unset=True)
            field_map = {
                "cat": "category", "price": "price_text", "descr": "description",
                "lat": "latitude", "lng": "longitude",
            }
            media = changes.pop("media", None)
            for name, value in changes.items():
                if name == "visibility" and account_type is AccountType.USER:
                    continue
                setattr(listing, field_map.get(name, name), value)
            listing.updated_at = datetime.now(UTC)
            if media is not None:
                attachments = [ListingMediaAttachment.model_validate(item) for item in media]
                await self._repository.replace_media(
                    session,
                    listing_id=listing.id,
                    media=self._validated_media(attachments, account_id, account_type),
                )
            await session.flush()
            await session.commit()
            await self._bump()
            return (await self._project(
                session,
                [listing],
                current_account_id=account_id,
            ))[0]

    async def delete(
        self,
        *,
        public_id: str,
        account_id: int,
        account_type: AccountType,
    ) -> None:
        async with self._session_factory() as session:
            listing = await self._owned(session, public_id, account_id, account_type)
            await session.delete(listing)
            await session.commit()
            await self._bump()

    async def toggle_save(
        self,
        *,
        public_id: str,
        account_id: int,
        account_type: AccountType,
    ) -> bool:
        async with self._session_factory() as session:
            listing = await self._resolve(session, public_id)
            if (
                listing is None
                or listing.status != "active"
                or listing.review_state is not ReviewState.READY
            ):
                raise ApiError(404, "listing_not_found", "E'lon topilmadi.")
            save_owner_id = await self._save_owner_account_id(
                session,
                account_id,
                account_type,
            )
            if save_owner_id is None:
                raise ApiError(
                    400,
                    "listing_save_user_unlinked",
                    "Oddiy kabinetingiz bilan bog'lanish topilmadi.",
                )
            saved = await self._repository.toggle_save(
                session,
                account_id=save_owner_id,
                listing_id=listing.id,
                created_at=datetime.now(UTC),
            )
            await session.flush()
            await session.commit()
            return saved

    async def _save_owner_account_id(
        self,
        session: AsyncSession,
        account_id: int | None,
        account_type: AccountType | None,
    ) -> int | None:
        if account_id is None:
            return None
        if account_type is AccountType.BUSINESS:
            return await self._repository.linked_user_account_id(
                session,
                business_account_id=account_id,
            )
        return account_id

    async def list_saved(self, *, account_id: int) -> list[ListingRead]:
        async with self._session_factory() as session:
            rows = await self._repository.list_saved(session, account_id=account_id)
            result = await self._project(session, rows, current_account_id=account_id)
            await session.rollback()
            return result

    async def _resolve(self, session: AsyncSession, public_id: str) -> Listing | None:
        if PUBLIC_ID_RE.fullmatch(public_id) is None:
            return None
        return await self._repository.by_public_id(
            session,
            public_id=public_id,
        )

    async def _owned(
        self,
        session: AsyncSession,
        public_id: str,
        account_id: int,
        account_type: AccountType,
    ) -> Listing:
        listing = await self._resolve(session, public_id)
        owned = listing is not None and (
            listing.owner_business_account_id == account_id
            if account_type is AccountType.BUSINESS
            else (
                listing.owner_user_account_id == account_id
                and listing.owner_business_account_id is None
            )
        )
        if not owned:
            raise ApiError(404, "listing_not_found", "E'lon topilmadi.")
        return listing

    def _validated_media(
        self,
        media: list[ListingMediaAttachment],
        account_id: int,
        account_type: AccountType,
    ) -> list[tuple[str, str]]:
        result = []
        for item in media[:10]:
            purpose = "listing_video" if item.type == "video" else "listing_photo"
            prefix = f"private/{account_type.value}/{account_id}/{purpose}/"
            if not item.object_key.startswith(prefix):
                raise ApiError(
                    403,
                    "listing_media_forbidden",
                    "Bu media obyekti akkauntga tegishli emas.",
                )
            result.append((item.type, item.object_key))
        return result

    async def _project(
        self,
        session: AsyncSession,
        rows: list[Listing],
        *,
        current_account_id: int | None,
    ) -> list[ListingRead]:
        listing_ids = [int(row.id) for row in rows]
        media = await self._repository.media(session, listing_ids)
        user_ids = {
            int(row.owner_user_account_id)
            for row in rows if row.owner_user_account_id is not None
        }
        business_ids = {
            int(row.owner_business_account_id)
            for row in rows if row.owner_business_account_id is not None
        }
        users = await self._repository.user_names(session, user_ids)
        businesses = await self._repository.business_names(session, business_ids)
        saved_ids = await self._repository.saved_ids(
            session,
            account_id=current_account_id,
            listing_ids=listing_ids,
        )
        result = []
        for row in rows:
            if row.owner_business_account_id is not None:
                owner_kind = "business"
                owner_id = int(row.owner_business_account_id)
                owner_name = businesses.get(owner_id, "")
                public_kind = PublicResultKind.BUSINESS
            else:
                owner_kind = "user"
                owner_id = int(row.owner_user_account_id or 0)
                owner_name = users.get(owner_id, "")
                public_kind = PublicResultKind.USER
            result.append(ListingRead(
                public_id=build_listing_public_id(int(row.id)),
                cat=(row.category if row.category in CATEGORIES else "boshqa"),
                title=row.title,
                price=row.price_text,
                descr=row.description,
                address=row.address,
                lat=row.latitude,
                lng=row.longitude,
                visibility=("own" if row.visibility == "own" else "all"),
                status=("inactive" if row.status == "inactive" else "active"),
                created_at=row.created_at,
                media=[
                    ListingMediaRead(
                        type=("video" if item.media_type == "video" else "photo"),
                        url=self._image_url_provider(item.object_key),
                    )
                    for item in media.get(int(row.id), [])
                ],
                owner_kind=owner_kind,
                owner_public_id=build_public_id(public_kind, owner_id),
                owner_name=owner_name,
                is_saved=int(row.id) in saved_ids,
            ))
        return result

    async def _bump(self) -> None:
        if self._cache_epoch is not None:
            await self._cache_epoch.bump()
