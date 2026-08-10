from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.profiles.model import BusinessProfile, UserProfile
from app.reviews.model import Review
from app.reviews.repository import ReviewRepository
from app.reviews.schemas import (
    MyReviewRead,
    ReviewListRead,
    ReviewMutationRead,
    ReviewRead,
    ReviewReplyWrite,
    ReviewTargetKind,
    ReviewWrite,
)


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NowProvider = Callable[[], datetime]


def review_average(rating_sum: int, rating_count: int) -> float:
    return round(rating_sum / rating_count, 1) if rating_count else 0


class ReviewService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: ReviewRepository | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or ReviewRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def public_list(
        self,
        *,
        target_kind: ReviewTargetKind,
        target_public_id: str,
        reviewer_account_id: int | None,
        reviewer_account_type: AccountType | None,
    ) -> ReviewListRead:
        async with self._session_factory() as session:
            target = await self._target(
                session, kind=target_kind, public_id=target_public_id
            )
            target_id = int(target.account_id)
            rows = await self._repository.reviews(
                session,
                kind=target_kind,
                target_account_id=target_id,
                limit=100,
            )
            total = sum(int(review.stars) for review, _name in rows)
            can_review = False
            mine = None
            if reviewer_account_id and reviewer_account_type is AccountType.USER:
                own = await self._repository.one_for_reviewer(
                    session,
                    kind=target_kind,
                    target_account_id=target_id,
                    reviewer_account_id=reviewer_account_id,
                )
                if own is not None:
                    mine = MyReviewRead(stars=own.stars, comment=own.comment)
                blocked = await self._self_review(
                    session,
                    kind=target_kind,
                    target_account_id=target_id,
                    reviewer_account_id=reviewer_account_id,
                )
                if not blocked:
                    can_review = await self._repository.eligible_order_id(
                        session,
                        reviewer_account_id=reviewer_account_id,
                        kind=target_kind,
                        target_account_id=target_id,
                    ) is not None
            return ReviewListRead(
                reviews=[self._read(review, name) for review, name in rows],
                avg=review_average(total, len(rows)),
                count=len(rows),
                can_review=can_review,
                my_review=mine,
            )

    async def save(
        self,
        *,
        reviewer_account_id: int,
        reviewer_account_type: AccountType,
        body: ReviewWrite,
    ) -> ReviewMutationRead:
        self._require_user(reviewer_account_type)
        async with self._session_factory() as session:
            target = await self._target(
                session,
                kind=body.target_kind,
                public_id=body.target_public_id,
            )
            target_id = int(target.account_id)
            if await self._self_review(
                session,
                kind=body.target_kind,
                target_account_id=target_id,
                reviewer_account_id=reviewer_account_id,
            ):
                message = (
                    "O‘z do‘koningizga baho bera olmaysiz."
                    if body.target_kind is ReviewTargetKind.BUSINESS
                    else "O‘zingizga baho bera olmaysiz."
                )
                raise ApiError(400, "review_self_forbidden", message)
            order_id = await self._repository.eligible_order_id(
                session,
                reviewer_account_id=reviewer_account_id,
                kind=body.target_kind,
                target_account_id=target_id,
            )
            if order_id is None:
                raise ApiError(
                    403,
                    "review_order_required",
                    "Faqat shu yerdan buyurtma/xarid qilganlar baho bera oladi.",
                )
            now = self._now_provider()
            review = await self._repository.one_for_reviewer(
                session,
                kind=body.target_kind,
                target_account_id=target_id,
                reviewer_account_id=reviewer_account_id,
                lock=True,
            )
            if review is None:
                session.add(Review(
                    target_kind=body.target_kind.value,
                    target_account_id=target_id,
                    reviewer_account_id=reviewer_account_id,
                    order_id=order_id,
                    stars=body.stars,
                    comment=body.comment,
                    owner_reply="",
                    owner_replied_at=None,
                    created_at=now,
                    updated_at=now,
                ))
            else:
                review.stars = body.stars
                review.comment = body.comment
                review.order_id = order_id
                review.updated_at = now
            await session.flush()
            result = await self._recompute(
                session, kind=body.target_kind, target_account_id=target_id
            )
            await session.commit()
            return result

    async def delete_own(
        self,
        *,
        reviewer_account_id: int,
        reviewer_account_type: AccountType,
        target_kind: ReviewTargetKind,
        target_public_id: str,
    ) -> ReviewMutationRead:
        self._require_user(reviewer_account_type)
        async with self._session_factory() as session:
            target = await self._target(
                session, kind=target_kind, public_id=target_public_id
            )
            target_id = int(target.account_id)
            review = await self._repository.one_for_reviewer(
                session,
                kind=target_kind,
                target_account_id=target_id,
                reviewer_account_id=reviewer_account_id,
                lock=True,
            )
            if review is not None:
                await self._repository.remove(session, review_id=int(review.id))
                await session.flush()
            result = await self._recompute(
                session, kind=target_kind, target_account_id=target_id
            )
            await session.commit()
            return result

    async def received(
        self,
        *,
        account_id: int,
        account_type: AccountType,
    ) -> ReviewListRead:
        kind = self._owner_kind(account_type)
        async with self._session_factory() as session:
            rows = await self._repository.reviews(
                session,
                kind=kind,
                target_account_id=account_id,
                limit=200,
            )
            total = sum(int(review.stars) for review, _name in rows)
            return ReviewListRead(
                reviews=[self._read(review, name) for review, name in rows],
                avg=review_average(total, len(rows)),
                count=len(rows),
            )

    async def reply(
        self,
        *,
        review_id: int,
        account_id: int,
        account_type: AccountType,
        body: ReviewReplyWrite,
    ) -> ReviewRead:
        kind = self._owner_kind(account_type)
        async with self._session_factory() as session:
            review = await self._repository.review(session, review_id=review_id)
            if (
                review is None
                or review.target_kind != kind.value
                or int(review.target_account_id) != account_id
            ):
                raise ApiError(404, "review_not_found", "Fikr topilmadi.")
            await self._repository.set_reply(
                session,
                review_id=review_id,
                reply=body.reply,
                now=self._now_provider(),
            )
            await session.flush()
            rows = await self._repository.reviews(
                session,
                kind=kind,
                target_account_id=account_id,
                limit=200,
            )
            projected = next(
                (self._read(row, name) for row, name in rows if row.id == review_id),
                None,
            )
            if projected is None:
                raise ApiError(404, "review_not_found", "Fikr topilmadi.")
            await session.commit()
            return projected

    async def _target(
        self,
        session: AsyncSession,
        *,
        kind: ReviewTargetKind,
        public_id: str,
    ) -> BusinessProfile | UserProfile:
        target = await self._repository.target(
            session, kind=kind, public_id=public_id
        )
        if target is None:
            raise ApiError(404, "review_target_not_found", "Obyekt topilmadi.")
        if (
            kind is ReviewTargetKind.SPECIALIST
            and not await self._repository.has_specialist(
                session,
                user_account_id=target.account_id,
            )
        ):
            raise ApiError(404, "review_target_not_found", "Obyekt topilmadi.")
        return target

    async def _self_review(
        self,
        session: AsyncSession,
        *,
        kind: ReviewTargetKind,
        target_account_id: int,
        reviewer_account_id: int,
    ) -> bool:
        if kind is ReviewTargetKind.SPECIALIST:
            return target_account_id == reviewer_account_id
        return await self._repository.owns_business(
            session,
            user_account_id=reviewer_account_id,
            business_account_id=target_account_id,
        )

    async def _recompute(
        self,
        session: AsyncSession,
        *,
        kind: ReviewTargetKind,
        target_account_id: int,
    ) -> ReviewMutationRead:
        rating_sum, rating_count = await self._repository.aggregate(
            session, kind=kind, target_account_id=target_account_id
        )
        await self._repository.persist_rating(
            session,
            kind=kind,
            target_account_id=target_account_id,
            rating_sum=rating_sum,
            rating_count=rating_count,
        )
        return ReviewMutationRead(
            avg=review_average(rating_sum, rating_count),
            count=rating_count,
        )

    @staticmethod
    def _read(review: Review, user_name: str | None) -> ReviewRead:
        return ReviewRead(
            id=int(review.id),
            stars=int(review.stars),
            comment=review.comment or "",
            user_name=user_name or "Foydalanuvchi",
            created_at=review.created_at,
            owner_reply=review.owner_reply or "",
            owner_replied_at=review.owner_replied_at,
        )

    @staticmethod
    def _owner_kind(account_type: AccountType) -> ReviewTargetKind:
        return (
            ReviewTargetKind.BUSINESS
            if account_type is AccountType.BUSINESS
            else ReviewTargetKind.SPECIALIST
        )

    @staticmethod
    def _require_user(account_type: AccountType) -> None:
        if account_type is not AccountType.USER:
            raise ApiError(
                403,
                "review_user_required",
                "Avval oddiy profilga o‘ting.",
            )
