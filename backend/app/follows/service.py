"""Obuna bo'lish va bekor qilish.

v1656 (`api.py:toggle_follow`) bitta amal beradi: obuna bo'lmagan
bo'lsa — bo'ladi, bo'lgan bo'lsa — bekor qiladi. Shu xatti-harakat
saqlangan, chunki ekran bitta tugma bilan ishlaydi.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
import time

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.core.errors import ApiError
from app.follows.model import ProfileFollow
from app.follows.schemas import FollowResult, FollowToggle
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile
from app.public_ids import build_profile_public_id


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class FollowService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        now: Callable[[], int] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._now = now or (lambda: int(time.time()))

    async def toggle(
        self,
        *,
        account_id: int,
        body: FollowToggle,
    ) -> FollowResult:
        raced = False
        async with self._session_factory() as session:
            target_id = await self._resolve_target(session, body)
            await self._guard_self_follow(
                session,
                account_id=account_id,
                target_id=target_id,
            )
            existing = await session.scalar(
                select(ProfileFollow).where(
                    ProfileFollow.follower_account_id == account_id,
                    ProfileFollow.target_account_id == target_id,
                )
            )
            following = existing is None
            if existing is not None:
                await session.execute(
                    delete(ProfileFollow).where(
                        ProfileFollow.id == existing.id
                    )
                )
            else:
                session.add(ProfileFollow(
                    follower_account_id=account_id,
                    target_account_id=target_id,
                    target_kind=body.kind,
                    created_at=self._now(),
                ))
                try:
                    await session.flush()
                except IntegrityError:
                    # Ikki so'rov bir vaqtda kelgan — natija bir xil.
                    await session.rollback()
                    raced = True
            if not raced:
                followers = await self._recount(
                    session,
                    account_id=account_id,
                    target_id=target_id,
                )
                response = FollowResult(
                    following=following,
                    followers=followers,
                )
                await session.commit()
                return response

        return await self._current_state(
            account_id=account_id,
            target_id=target_id,
        )

    async def _current_state(
        self,
        *,
        account_id: int,
        target_id: int,
    ) -> FollowResult:
        async with self._session_factory() as session:
            exists = await session.scalar(
                select(func.count(ProfileFollow.id)).where(
                    ProfileFollow.follower_account_id == account_id,
                    ProfileFollow.target_account_id == target_id,
                )
            )
            followers = await self._followers_count(session, target_id)
            await session.rollback()
            return FollowResult(
                following=bool(exists),
                followers=followers,
            )

    async def _resolve_target(
        self,
        session: AsyncSession,
        body: FollowToggle,
    ) -> int:
        account_type = (
            AccountType.BUSINESS if body.kind == "business" else AccountType.USER
        )
        model = BusinessProfile if body.kind == "business" else UserProfile
        target_id = await session.scalar(
            select(model.account_id)
            .join(Account, Account.id == model.account_id)
            .where(
                model.public_id == body.public_id,
                Account.status == "active",
                Account.account_type == account_type,
            )
        )
        if target_id is None:
            raise ApiError(
                404,
                "follow_target_not_found",
                "Obuna bo'linadigan profil topilmadi.",
            )
        return int(target_id)

    async def _guard_self_follow(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        target_id: int,
    ) -> None:
        if account_id == target_id:
            raise ApiError(
                400,
                "follow_self_forbidden",
                "O'zingizga obuna bo'la olmaysiz.",
            )
        # v1656: biznes egasi o'zining oddiy profiliga (va aksincha)
        # obuna bo'la olmaydi — ular bitta odam.
        linked = await session.scalar(
            select(func.count(ProfileLink.user_account_id)).where(
                (
                    (ProfileLink.user_account_id == account_id)
                    & (ProfileLink.business_account_id == target_id)
                )
                | (
                    (ProfileLink.business_account_id == account_id)
                    & (ProfileLink.user_account_id == target_id)
                )
            )
        )
        if linked:
            raise ApiError(
                400,
                "follow_self_forbidden",
                "O'z profilingizga obuna bo'lib bo'lmaydi.",
            )

    async def _recount(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        target_id: int,
    ) -> int:
        """Obunachi va nishon hisoblagichlarini jadvaldan qayta hisoblaydi."""
        await session.flush()
        followers = await self._followers_count(session, target_id)
        following = await session.scalar(
            select(func.count(ProfileFollow.id)).where(
                ProfileFollow.follower_account_id == account_id
            )
        )
        for identifier, field, value in (
            (target_id, "followers_count", followers),
            (account_id, "following_count", int(following or 0)),
        ):
            for model in (UserProfile, BusinessProfile):
                profile = await session.get(model, identifier)
                if profile is not None:
                    setattr(profile, field, value)
        return followers

    @staticmethod
    async def _followers_count(session: AsyncSession, target_id: int) -> int:
        value = await session.scalar(
            select(func.count(ProfileFollow.id)).where(
                ProfileFollow.target_account_id == target_id
            )
        )
        return int(value or 0)

    async def is_following(
        self,
        session: AsyncSession,
        *,
        account_id: int | None,
        target_id: int,
    ) -> bool:
        if account_id is None:
            return False
        value = await session.scalar(
            select(func.count(ProfileFollow.id)).where(
                ProfileFollow.follower_account_id == account_id,
                ProfileFollow.target_account_id == target_id,
            )
        )
        return bool(value)


def target_public_id(kind: str, account_id: int) -> str:
    return build_profile_public_id(kind, account_id)
