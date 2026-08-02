from __future__ import annotations

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.legacy_migration.model import ReviewState
from app.listings.model import Listing, ListingMedia, ListingSave
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile


class ListingRepository:
    async def counts(self, session: AsyncSession) -> dict[str, int]:
        rows = (await session.execute(
            select(Listing.category, func.count(Listing.id))
            .where(
                Listing.status == "active",
                Listing.visibility == "all",
                Listing.review_state == ReviewState.READY,
            )
            .group_by(Listing.category)
        )).all()
        return {str(category): int(count) for category, count in rows}

    async def list_public(
        self,
        session: AsyncSession,
        *,
        category: str = "",
        query: str = "",
    ) -> list[Listing]:
        statement = select(Listing).where(
            Listing.status == "active",
            Listing.visibility == "all",
            Listing.review_state == ReviewState.READY,
        )
        if category:
            statement = statement.where(Listing.category == category)
        if query:
            pattern = f"%{query.casefold()}%"
            statement = statement.where(or_(
                func.lower(Listing.title).like(pattern),
                func.lower(Listing.description).like(pattern),
                func.lower(Listing.address).like(pattern),
                func.lower(Listing.price_text).like(pattern),
            ))
        return list((await session.scalars(
            statement.order_by(Listing.created_at.desc(), Listing.id.desc()).limit(100)
        )).all())

    async def by_public_id(
        self,
        session: AsyncSession,
        *,
        public_id: str,
    ) -> Listing | None:
        return await session.scalar(
            select(Listing)
            .where(Listing.public_id == public_id)
            .limit(1)
        )

    async def list_owner(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: str,
    ) -> list[Listing]:
        owner = (
            Listing.owner_business_account_id == account_id
            if account_type == "business"
            else (
                (Listing.owner_user_account_id == account_id)
                & Listing.owner_business_account_id.is_(None)
            )
        )
        return list((await session.scalars(
            select(Listing)
            .where(owner)
            .order_by(Listing.created_at.desc(), Listing.id.desc())
        )).all())

    async def media(
        self,
        session: AsyncSession,
        listing_ids: list[int],
    ) -> dict[int, list[ListingMedia]]:
        if not listing_ids:
            return {}
        rows = list((await session.scalars(
            select(ListingMedia)
            .where(ListingMedia.listing_id.in_(listing_ids))
            .order_by(ListingMedia.listing_id, ListingMedia.position, ListingMedia.id)
        )).all())
        result: dict[int, list[ListingMedia]] = {}
        for row in rows:
            result.setdefault(int(row.listing_id), []).append(row)
        return result

    async def user_names(
        self,
        session: AsyncSession,
        account_ids: set[int],
    ) -> dict[int, str]:
        if not account_ids:
            return {}
        rows = (await session.execute(
            select(UserProfile.account_id, UserProfile.name)
            .where(UserProfile.account_id.in_(account_ids))
        )).all()
        return {int(account_id): str(name) for account_id, name in rows}

    async def business_names(
        self,
        session: AsyncSession,
        account_ids: set[int],
    ) -> dict[int, str]:
        if not account_ids:
            return {}
        rows = (await session.execute(
            select(BusinessProfile.account_id, BusinessProfile.name)
            .where(BusinessProfile.account_id.in_(account_ids))
        )).all()
        return {int(account_id): str(name) for account_id, name in rows}

    async def saved_ids(
        self,
        session: AsyncSession,
        *,
        account_id: int | None,
        listing_ids: list[int],
    ) -> set[int]:
        if account_id is None or not listing_ids:
            return set()
        return {int(value) for value in (await session.scalars(
            select(ListingSave.listing_id).where(
                ListingSave.owner_user_account_id == account_id,
                ListingSave.listing_id.in_(listing_ids),
            )
        )).all()}

    async def linked_user_account_id(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
    ) -> int | None:
        value = await session.scalar(
            select(ProfileLink.user_account_id).where(
                ProfileLink.business_account_id == business_account_id,
            )
        )
        return int(value) if value is not None else None

    async def replace_media(
        self,
        session: AsyncSession,
        *,
        listing_id: int,
        media: list[tuple[str, str]],
    ) -> None:
        await session.execute(
            delete(ListingMedia).where(ListingMedia.listing_id == listing_id)
        )
        for position, (media_type, object_key) in enumerate(media):
            session.add(ListingMedia(
                listing_id=listing_id,
                media_type=media_type,
                object_key=object_key,
                position=position,
                migration_state="copied",
                migration_run_id=None,
            ))

    async def toggle_save(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        listing_id: int,
        created_at,
    ) -> bool:
        existing = await session.scalar(
            select(ListingSave).where(
                ListingSave.owner_user_account_id == account_id,
                ListingSave.listing_id == listing_id,
            )
        )
        if existing is not None:
            await session.delete(existing)
            return False
        session.add(ListingSave(
            owner_user_account_id=account_id,
            listing_id=listing_id,
            created_at=created_at,
        ))
        return True

    async def list_saved(
        self,
        session: AsyncSession,
        *,
        account_id: int,
    ) -> list[Listing]:
        return list((await session.scalars(
            select(Listing)
            .join(ListingSave, ListingSave.listing_id == Listing.id)
            .where(
                ListingSave.owner_user_account_id == account_id,
                Listing.status == "active",
                Listing.review_state == ReviewState.READY,
            )
            .order_by(ListingSave.created_at.desc(), Listing.id.desc())
        )).all())
