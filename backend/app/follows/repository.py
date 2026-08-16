"""Obunachilar va kuzatilayotgan profillar uchun indeksli so'rovlar."""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import case, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.follows.model import ProfileFollow
from app.profiles.model import BusinessProfile, UserProfile

FollowListKind = Literal["followers", "following"]


class FollowRepository:
    async def list_profiles(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        list_kind: FollowListKind,
    ) -> tuple[list[dict[str, Any]], int]:
        """Ikki profil turini N+1siz bitta UNION so'rovida qaytaradi."""
        owner_column = (
            ProfileFollow.follower_account_id
            if list_kind == "followers"
            else ProfileFollow.target_account_id
        )
        relation_filter = (
            ProfileFollow.target_account_id == account_id
            if list_kind == "followers"
            else ProfileFollow.follower_account_id == account_id
        )

        user_rows = (
            select(
                literal("user").label("kind"),
                UserProfile.account_id.label("profile_account_id"),
                UserProfile.public_id.label("public_id"),
                UserProfile.name.label("name"),
                UserProfile.public_username.label("info"),
                UserProfile.avatar_object_key.label("image_object_key"),
                UserProfile.avatar_x.label("crop_x"),
                UserProfile.avatar_y.label("crop_y"),
                UserProfile.avatar_zoom.label("crop_zoom"),
                ProfileFollow.created_at.label("followed_at"),
                ProfileFollow.id.label("follow_id"),
            )
            .join(Account, Account.id == owner_column)
            .join(UserProfile, UserProfile.account_id == owner_column)
            .where(
                relation_filter,
                Account.account_type == AccountType.USER,
                Account.status == "active",
            )
        )
        business_rows = (
            select(
                literal("business").label("kind"),
                BusinessProfile.account_id.label("profile_account_id"),
                BusinessProfile.public_id.label("public_id"),
                BusinessProfile.name.label("name"),
                BusinessProfile.direction.label("info"),
                BusinessProfile.logo_object_key.label("image_object_key"),
                BusinessProfile.logo_x.label("crop_x"),
                BusinessProfile.logo_y.label("crop_y"),
                BusinessProfile.logo_zoom.label("crop_zoom"),
                ProfileFollow.created_at.label("followed_at"),
                ProfileFollow.id.label("follow_id"),
            )
            .join(Account, Account.id == owner_column)
            .join(BusinessProfile, BusinessProfile.account_id == owner_column)
            .where(
                relation_filter,
                Account.account_type == AccountType.BUSINESS,
                Account.status == "active",
            )
        )
        profiles = union_all(user_rows, business_rows).subquery()
        order_by = [profiles.c.followed_at.desc(), profiles.c.follow_id.desc()]
        if list_kind == "followers":
            # v1656 avval oddiy, keyin biznes obunachilarni chiqaradi.
            order_by.insert(
                0,
                case((profiles.c.kind == "user", 0), else_=1),
            )
        result = await session.execute(
            select(profiles, func.count().over().label("total"))
            .order_by(*order_by)
        )
        rows = [dict(row) for row in result.mappings().all()]
        total = int(rows[0]["total"]) if rows else 0
        return rows, total
