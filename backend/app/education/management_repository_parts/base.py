"""Umumiy asos: biznes profilini topish."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.profiles.model import BusinessProfile


class EducationManagementRepositoryBase:
    async def profile(
        self,
        session: AsyncSession,
        business_account_id: int,
    ) -> BusinessProfile | None:
        return await session.get(BusinessProfile, business_account_id)
