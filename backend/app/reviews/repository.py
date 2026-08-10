from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.orders.model import Order
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile
from app.reviews.model import Review
from app.reviews.schemas import ReviewTargetKind
from app.specialists.model import SpecialistProfile


class ReviewRepository:
    async def has_specialist(
        self,
        session: AsyncSession,
        *,
        user_account_id: int,
    ) -> bool:
        return bool(await session.scalar(
            select(SpecialistProfile.user_account_id).where(
                SpecialistProfile.user_account_id == user_account_id,
            )
        ))

    async def target(
        self,
        session: AsyncSession,
        *,
        kind: ReviewTargetKind,
        public_id: str,
    ) -> BusinessProfile | UserProfile | None:
        model = (
            BusinessProfile
            if kind is ReviewTargetKind.BUSINESS
            else UserProfile
        )
        account_type = (
            AccountType.BUSINESS
            if kind is ReviewTargetKind.BUSINESS
            else AccountType.USER
        )
        return await session.scalar(
            select(model)
            .join(Account, Account.id == model.account_id)
            .where(
                model.public_id == public_id,
                Account.account_type == account_type,
                Account.status == "active",
            )
            .limit(1)
        )

    async def reviews(
        self,
        session: AsyncSession,
        *,
        kind: ReviewTargetKind,
        target_account_id: int,
        limit: int,
    ) -> list[tuple[Review, str]]:
        return list((await session.execute(
            select(Review, UserProfile.name)
            .outerjoin(
                UserProfile,
                UserProfile.account_id == Review.reviewer_account_id,
            )
            .where(
                Review.target_kind == kind.value,
                Review.target_account_id == target_account_id,
            )
            .order_by(Review.id.desc())
            .limit(limit)
        )).all())

    async def one_for_reviewer(
        self,
        session: AsyncSession,
        *,
        kind: ReviewTargetKind,
        target_account_id: int,
        reviewer_account_id: int,
        lock: bool = False,
    ) -> Review | None:
        statement = select(Review).where(
            Review.target_kind == kind.value,
            Review.target_account_id == target_account_id,
            Review.reviewer_account_id == reviewer_account_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def review(self, session: AsyncSession, *, review_id: int) -> Review | None:
        return await session.scalar(
            select(Review).where(Review.id == review_id).with_for_update()
        )

    async def eligible_order_id(
        self,
        session: AsyncSession,
        *,
        reviewer_account_id: int,
        kind: ReviewTargetKind,
        target_account_id: int,
    ) -> int | None:
        provider_kind = "business" if kind is ReviewTargetKind.BUSINESS else "user"
        value = await session.scalar(
            select(Order.id)
            .where(
                Order.customer_account_id == reviewer_account_id,
                Order.customer_kind == "user",
                Order.provider_account_id == target_account_id,
                Order.provider_kind == provider_kind,
                Order.status.not_in(("cancelled", "rejected")),
            )
            .order_by(Order.id.desc())
            .limit(1)
        )
        return int(value) if value is not None else None

    async def owns_business(
        self,
        session: AsyncSession,
        *,
        user_account_id: int,
        business_account_id: int,
    ) -> bool:
        return bool(await session.scalar(
            select(ProfileLink.user_account_id).where(
                ProfileLink.user_account_id == user_account_id,
                ProfileLink.business_account_id == business_account_id,
            )
        ))

    async def aggregate(
        self,
        session: AsyncSession,
        *,
        kind: ReviewTargetKind,
        target_account_id: int,
    ) -> tuple[int, int]:
        total, count = (await session.execute(
            select(func.coalesce(func.sum(Review.stars), 0), func.count(Review.id))
            .where(
                Review.target_kind == kind.value,
                Review.target_account_id == target_account_id,
            )
        )).one()
        return int(total or 0), int(count or 0)

    async def persist_rating(
        self,
        session: AsyncSession,
        *,
        kind: ReviewTargetKind,
        target_account_id: int,
        rating_sum: int,
        rating_count: int,
    ) -> None:
        if kind is ReviewTargetKind.BUSINESS:
            statement = update(BusinessProfile).where(
                BusinessProfile.account_id == target_account_id
            ).values(rating_sum=rating_sum, rating_count=rating_count)
        else:
            statement = update(UserProfile).where(
                UserProfile.account_id == target_account_id
            ).values(
                specialist_rating_sum=rating_sum,
                specialist_rating_count=rating_count,
            )
        await session.execute(statement)

    async def remove(self, session: AsyncSession, *, review_id: int) -> None:
        await session.execute(delete(Review).where(Review.id == review_id))

    async def set_reply(
        self,
        session: AsyncSession,
        *,
        review_id: int,
        reply: str,
        now: datetime,
    ) -> None:
        await session.execute(
            update(Review)
            .where(Review.id == review_id)
            .values(owner_reply=reply, owner_replied_at=now, updated_at=now)
        )
