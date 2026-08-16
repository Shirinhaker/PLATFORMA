from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account
from app.core.errors import ApiError
from app.specialists.model import (
    SpecialistCredential,
    SpecialistOffer,
    SpecialistPortfolio,
    SpecialistProfile,
)
from app.specialists.repository import SpecialistRepository
from app.specialists.schemas import (
    CreatedRead,
    MutationRead,
    SpecialistCredentialCreate,
    SpecialistCredentialRead,
    SpecialistOfferRead,
    SpecialistOfferWrite,
    SpecialistPortfolioCreate,
    SpecialistPortfolioRead,
    SpecialistProfileWrite,
    SpecialistRead,
)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
ImageUrlProvider = Callable[[str], str]
ObjectDeleter = Callable[[str], None]
NowProvider = Callable[[], datetime]


class SpecialistService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: SpecialistRepository | None = None,
        image_url_provider: ImageUrlProvider | None = None,
        object_deleter: ObjectDeleter | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or SpecialistRepository()
        self._image_url_provider = image_url_provider or (
            lambda key: f"/media/{key}" if key else ""
        )
        self._object_deleter = object_deleter or (lambda _key: None)
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def get(self, *, user_account_id: int) -> SpecialistRead:
        async with self._session_factory() as session:
            profile = await self._repository.profile(
                session, user_account_id=user_account_id,
            )
            credentials, offers, portfolio = await self._repository.content(
                session, user_account_id=user_account_id,
            )
            review_count = await self._repository.review_count(
                session, user_account_id=user_account_id,
            )
            result = self._read(
                profile, credentials, offers, portfolio, review_count,
            )
            await session.rollback()
            return result

    async def update_profile(
        self,
        *,
        user_account_id: int,
        body: SpecialistProfileWrite,
    ) -> SpecialistRead:
        if body.visible and not body.profession:
            raise ApiError(
                400,
                "specialist_profession_required",
                "Ko'rinish uchun kasb/yo'nalish kiritilishi shart.",
            )
        async with self._session_factory() as session:
            try:
                await self._lock_owner(session, user_account_id)
                profile = await self._repository.profile(
                    session, user_account_id=user_account_id, lock=True,
                )
                now = self._now_provider()
                if profile is None:
                    profile = SpecialistProfile(
                        user_account_id=user_account_id,
                        profession=body.profession,
                        description=body.description,
                        price_text="",
                        service_area="",
                        is_government=False,
                        organization="",
                        department="",
                        position="",
                        work_hours="",
                        after_hours="",
                        visible=body.visible,
                        available=True,
                        latitude=body.latitude,
                        longitude=body.longitude,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(profile)
                else:
                    profile.profession = body.profession
                    profile.description = body.description
                    profile.visible = body.visible
                    profile.latitude = body.latitude
                    profile.longitude = body.longitude
                    profile.updated_at = now
                await session.flush()
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        return await self.get(user_account_id=user_account_id)

    async def add_credential(
        self,
        *,
        user_account_id: int,
        body: SpecialistCredentialCreate,
    ) -> CreatedRead:
        self._require_owned_key(user_account_id, body.object_key, "specialist_credential")
        async with self._session_factory() as session:
            try:
                await self._lock_owner(session, user_account_id)
                count = await self._repository.credential_count(
                    session, user_account_id=user_account_id,
                )
                if count >= 12:
                    raise ApiError(
                        400,
                        "specialist_credential_limit",
                        "Tasdiqlovchi hujjatlar 12 tadan oshmasin.",
                    )
                row = SpecialistCredential(
                    user_account_id=user_account_id,
                    legacy_source_id=None,
                    object_key=body.object_key,
                    legacy_media_url="",
                    position=count,
                    created_at=self._now_provider(),
                )
                session.add(row)
                await session.flush()
                row_id = int(row.id)
                await session.commit()
                return CreatedRead(id=row_id)
            except Exception:
                await session.rollback()
                raise

    async def delete_credential(self, *, user_account_id: int, row_id: int) -> None:
        key = ""
        async with self._session_factory() as session:
            try:
                row = await self._repository.credential(
                    session,
                    user_account_id=user_account_id,
                    row_id=row_id,
                    lock=True,
                )
                if row is None:
                    raise ApiError(404, "specialist_credential_not_found", "Hujjat rasmi topilmadi.")
                key = row.object_key
                await session.delete(row)
                await session.flush()
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        self._delete_safely(key)

    async def create_offer(
        self,
        *,
        user_account_id: int,
        body: SpecialistOfferWrite,
    ) -> CreatedRead:
        image_object_key = "" if body.clear_image else body.image_object_key
        if image_object_key:
            self._require_owned_key(
                user_account_id, image_object_key, "specialist_offer_image",
            )
        async with self._session_factory() as session:
            try:
                await self._lock_owner(session, user_account_id)
                count = await self._repository.offer_count(
                    session, user_account_id=user_account_id,
                )
                if count >= 60:
                    raise ApiError(
                        400,
                        "specialist_offer_limit",
                        "Mahsulot va xizmatlar 60 tadan oshmasin.",
                    )
                now = self._now_provider()
                row = SpecialistOffer(
                    user_account_id=user_account_id,
                    legacy_source_id=None,
                    kind=body.kind,
                    name=body.name,
                    price_text=body.price_text,
                    note=body.note,
                    image_object_key=image_object_key,
                    legacy_image_url="",
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                await session.flush()
                row_id = int(row.id)
                await session.commit()
                return CreatedRead(id=row_id)
            except Exception:
                await session.rollback()
                raise

    async def update_offer(
        self,
        *,
        user_account_id: int,
        row_id: int,
        body: SpecialistOfferWrite,
    ) -> MutationRead:
        image_object_key = "" if body.clear_image else body.image_object_key
        if image_object_key:
            self._require_owned_key(
                user_account_id, image_object_key, "specialist_offer_image",
            )
        old_key = ""
        async with self._session_factory() as session:
            try:
                row = await self._repository.offer(
                    session,
                    user_account_id=user_account_id,
                    row_id=row_id,
                    lock=True,
                )
                if row is None:
                    raise ApiError(404, "specialist_offer_not_found", "Mahsulot/xizmat topilmadi.")
                if row.image_object_key != image_object_key or body.clear_image:
                    old_key = row.image_object_key
                    row.legacy_image_url = ""
                row.kind = body.kind
                row.name = body.name
                row.price_text = body.price_text
                row.note = body.note
                row.image_object_key = image_object_key
                row.updated_at = self._now_provider()
                await session.flush()
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        self._delete_safely(old_key)
        return MutationRead()

    async def delete_offer(self, *, user_account_id: int, row_id: int) -> None:
        key = ""
        async with self._session_factory() as session:
            try:
                row = await self._repository.offer(
                    session,
                    user_account_id=user_account_id,
                    row_id=row_id,
                    lock=True,
                )
                if row is None:
                    raise ApiError(404, "specialist_offer_not_found", "Mahsulot/xizmat topilmadi.")
                key = row.image_object_key
                await session.delete(row)
                await session.flush()
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        self._delete_safely(key)

    async def add_portfolio(
        self,
        *,
        user_account_id: int,
        body: SpecialistPortfolioCreate,
    ) -> CreatedRead:
        purpose = (
            "specialist_portfolio_video"
            if body.media_type == "video"
            else "specialist_portfolio_image"
        )
        self._require_owned_key(user_account_id, body.object_key, purpose)
        async with self._session_factory() as session:
            try:
                await self._lock_owner(session, user_account_id)
                count = await self._repository.portfolio_count(
                    session, user_account_id=user_account_id,
                )
                if count >= 40:
                    raise ApiError(
                        400,
                        "specialist_portfolio_limit",
                        "Bajarilgan ishlar media fayllari 40 tadan oshmasin.",
                    )
                row = SpecialistPortfolio(
                    user_account_id=user_account_id,
                    legacy_source_id=None,
                    media_type=body.media_type,
                    object_key=body.object_key,
                    legacy_media_url="",
                    created_at=self._now_provider(),
                )
                session.add(row)
                await session.flush()
                row_id = int(row.id)
                await session.commit()
                return CreatedRead(id=row_id)
            except Exception:
                await session.rollback()
                raise

    async def delete_portfolio(self, *, user_account_id: int, row_id: int) -> None:
        key = ""
        async with self._session_factory() as session:
            try:
                row = await self._repository.portfolio_item(
                    session,
                    user_account_id=user_account_id,
                    row_id=row_id,
                    lock=True,
                )
                if row is None:
                    raise ApiError(404, "specialist_portfolio_not_found", "Ish namunasi topilmadi.")
                key = row.object_key
                await session.delete(row)
                await session.flush()
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        self._delete_safely(key)

    async def _lock_owner(self, session: AsyncSession, user_account_id: int) -> None:
        owner = await session.get(Account, user_account_id, with_for_update=True)
        if owner is None:
            raise ApiError(404, "account_not_found", "Akkaunt topilmadi.")

    @staticmethod
    def _require_owned_key(user_account_id: int, object_key: str, purpose: str) -> None:
        prefix = f"private/user/{user_account_id}/{purpose}/"
        if not object_key.startswith(prefix):
            raise ApiError(
                403,
                "specialist_media_forbidden",
                "Bu media obyekti akkauntga tegishli emas.",
            )

    def _media_url(self, object_key: str, legacy_url: str) -> str:
        return self._image_url_provider(object_key) if object_key else legacy_url

    def _read(self, profile, credentials, offers, portfolio, review_count: int) -> SpecialistRead:
        return SpecialistRead(
            exists=profile is not None,
            profession=profile.profession if profile else "",
            description=profile.description if profile else "",
            visible=bool(profile.visible) if profile else False,
            latitude=profile.latitude if profile else None,
            longitude=profile.longitude if profile else None,
            review_count=review_count,
            credentials=[
                SpecialistCredentialRead(
                    id=row.id,
                    image_url=self._media_url(row.object_key, row.legacy_media_url),
                    position=row.position,
                    created_at=row.created_at,
                ) for row in credentials
            ],
            offers=[
                SpecialistOfferRead(
                    id=row.id,
                    kind=row.kind,
                    name=row.name,
                    price_text=row.price_text,
                    note=row.note,
                    image_url=self._media_url(row.image_object_key, row.legacy_image_url),
                    image_object_key=row.image_object_key,
                    created_at=row.created_at,
                ) for row in offers
            ],
            portfolio=[
                SpecialistPortfolioRead(
                    id=row.id,
                    media_type=row.media_type,
                    media_url=self._media_url(row.object_key, row.legacy_media_url),
                    created_at=row.created_at,
                ) for row in portfolio
            ],
        )

    def _delete_safely(self, object_key: str) -> None:
        if not object_key:
            return
        try:
            self._object_deleter(object_key)
        except Exception:
            pass
