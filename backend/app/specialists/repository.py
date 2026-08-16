from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.reviews.model import Review
from app.specialists.model import (
    SpecialistCredential,
    SpecialistOffer,
    SpecialistPortfolio,
    SpecialistProfile,
)


class SpecialistRepository:
    async def profile(
        self,
        session: AsyncSession,
        *,
        user_account_id: int,
        lock: bool = False,
    ) -> SpecialistProfile | None:
        statement = select(SpecialistProfile).where(
            SpecialistProfile.user_account_id == user_account_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def content(self, session: AsyncSession, *, user_account_id: int):
        credentials = list(
            (
                await session.scalars(
                    select(SpecialistCredential)
                    .where(SpecialistCredential.user_account_id == user_account_id)
                    .order_by(SpecialistCredential.position, SpecialistCredential.id)
                )
            ).all()
        )
        offers = list(
            (
                await session.scalars(
                    select(SpecialistOffer)
                    .where(SpecialistOffer.user_account_id == user_account_id)
                    .order_by(SpecialistOffer.created_at, SpecialistOffer.id)
                )
            ).all()
        )
        portfolio = list(
            (
                await session.scalars(
                    select(SpecialistPortfolio)
                    .where(SpecialistPortfolio.user_account_id == user_account_id)
                    .order_by(SpecialistPortfolio.created_at, SpecialistPortfolio.id)
                )
            ).all()
        )
        return credentials, offers, portfolio

    async def review_count(self, session: AsyncSession, *, user_account_id: int) -> int:
        return int(
            await session.scalar(
                select(func.count(Review.id)).where(
                    Review.target_kind == "specialist",
                    Review.target_account_id == user_account_id,
                )
            )
            or 0
        )

    async def credential_count(
        self, session: AsyncSession, *, user_account_id: int
    ) -> int:
        return int(
            await session.scalar(
                select(func.count(SpecialistCredential.id)).where(
                    SpecialistCredential.user_account_id == user_account_id,
                )
            )
            or 0
        )

    async def offer_count(self, session: AsyncSession, *, user_account_id: int) -> int:
        return int(
            await session.scalar(
                select(func.count(SpecialistOffer.id)).where(
                    SpecialistOffer.user_account_id == user_account_id,
                )
            )
            or 0
        )

    async def portfolio_count(
        self, session: AsyncSession, *, user_account_id: int
    ) -> int:
        return int(
            await session.scalar(
                select(func.count(SpecialistPortfolio.id)).where(
                    SpecialistPortfolio.user_account_id == user_account_id,
                )
            )
            or 0
        )

    async def credential(
        self,
        session: AsyncSession,
        *,
        user_account_id: int,
        row_id: int,
        lock: bool = False,
    ):
        statement = select(SpecialistCredential).where(
            SpecialistCredential.id == row_id,
            SpecialistCredential.user_account_id == user_account_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def offer(
        self,
        session: AsyncSession,
        *,
        user_account_id: int,
        row_id: int,
        lock: bool = False,
    ):
        statement = select(SpecialistOffer).where(
            SpecialistOffer.id == row_id,
            SpecialistOffer.user_account_id == user_account_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def portfolio_item(
        self,
        session: AsyncSession,
        *,
        user_account_id: int,
        row_id: int,
        lock: bool = False,
    ):
        statement = select(SpecialistPortfolio).where(
            SpecialistPortfolio.id == row_id,
            SpecialistPortfolio.user_account_id == user_account_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)
