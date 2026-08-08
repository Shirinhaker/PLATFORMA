"""E'lon to'lovi tasdiqlangach uni public ro'yxatlarga chiqaradi.

v1656 `payment_api.py:951` da shu mantiq bor edi, lekin uni ishlatadigan
oqim yo'q edi — e'lon darhol `active` bo'lib yaratilardi va `listing_publish`
narxi hech qachon qo'llanmasdi.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.listings.model import Listing


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class ListingActivationService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._now = now_provider

    async def resolve_owned(
        self,
        session: AsyncSession,
        *,
        public_id: str,
        account_id: int,
    ) -> int:
        """`l_…` kalitini ichki raqamga aylantiradi.

        Ochiq kontraktda e'lonning ichki raqami yo'q (`ListingRead` faqat
        `public_id` beradi), shuning uchun to'lov so'rovi kalit bilan
        keladi va egalik shu yerda tekshiriladi.
        """
        listing = await session.scalar(
            select(Listing).where(Listing.public_id == public_id)
        )
        owner = listing and (
            listing.owner_user_account_id
            or listing.owner_business_account_id
        )
        if listing is None or owner != account_id:
            raise ApiError(404, "listing_not_found", "E’lon topilmadi.")
        return listing.id

    async def activate_paid(
        self,
        session: AsyncSession,
        *,
        listing_id: int,
        account_id: int,
        now: int,
    ) -> None:
        """Chaqiruvchining tranzaksiyasida ishlaydi — to'lov bilan birga."""
        listing = await session.scalar(
            select(Listing)
            .where(Listing.id == listing_id)
            .with_for_update()
        )
        if listing is None or listing.status != "payment_pending":
            raise ApiError(
                409,
                "listing_not_pending",
                "Kutilayotgan e’lon topilmadi.",
            )
        owner = (
            listing.owner_user_account_id
            or listing.owner_business_account_id
        )
        if owner != account_id:
            raise ApiError(
                409,
                "listing_owner_mismatch",
                "E’lon to‘lov egasiga tegishli emas.",
            )
        listing.status = "active"
        listing.updated_at = datetime.fromtimestamp(now, UTC)
