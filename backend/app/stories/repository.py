from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account
from app.follows.model import ProfileFollow
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile
from app.stories.model import Story, StoryReport, StoryView


class StoryRepository:
    async def lock_owner(self, session: AsyncSession, account_id: int) -> None:
        await session.scalar(
            select(Account.id).where(Account.id == account_id).with_for_update()
        )

    async def active_count(
        self,
        session: AsyncSession,
        *,
        owner_account_id: int,
        now: datetime,
    ) -> int:
        value = await session.scalar(
            select(func.count(Story.id)).where(
                Story.owner_account_id == owner_account_id,
                Story.status.in_(("processing", "active")),
                Story.deleted_at.is_(None),
                Story.expires_at > now,
            )
        )
        return int(value or 0)

    async def active_story(
        self,
        session: AsyncSession,
        story_id: int,
        now: datetime,
    ) -> Story | None:
        return await session.scalar(
            select(Story).where(
                Story.id == story_id,
                Story.status == "active",
                Story.deleted_at.is_(None),
                Story.expires_at > now,
            )
        )

    async def managed_story(
        self,
        session: AsyncSession,
        *,
        story_id: int,
        owner_account_id: int,
    ) -> Story | None:
        return await session.scalar(
            select(Story).where(
                Story.id == story_id,
                Story.owner_account_id == owner_account_id,
                Story.status == "active",
                Story.deleted_at.is_(None),
            )
        )

    async def feed_rows(
        self,
        session: AsyncSession,
        *,
        viewer_account_id: int | None,
        now: datetime,
    ) -> list[tuple[Story, bool]]:
        viewed = StoryView.id.is_not(None)
        statement = (
            select(Story, viewed)
            .outerjoin(
                StoryView,
                (StoryView.story_id == Story.id)
                & (StoryView.viewer_account_id == (viewer_account_id or 0)),
            )
            .where(
                Story.status == "active",
                Story.deleted_at.is_(None),
                Story.expires_at > now,
            )
            .order_by(Story.created_at, Story.id)
        )
        return [(story, bool(seen)) for story, seen in (await session.execute(statement)).all()]

    async def owner_rows(
        self,
        session: AsyncSession,
        *,
        owner_account_id: int,
        viewer_account_id: int | None,
        now: datetime,
    ) -> list[tuple[Story, bool]]:
        statement = (
            select(Story, StoryView.id.is_not(None))
            .outerjoin(
                StoryView,
                (StoryView.story_id == Story.id)
                & (StoryView.viewer_account_id == (viewer_account_id or 0)),
            )
            .where(
                Story.owner_account_id == owner_account_id,
                Story.status == "active",
                Story.deleted_at.is_(None),
                Story.expires_at > now,
            )
            .order_by(Story.created_at, Story.id)
        )
        return [(story, bool(seen)) for story, seen in (await session.execute(statement)).all()]

    async def managed_rows(
        self,
        session: AsyncSession,
        *,
        owner_account_id: int,
        state: str,
        now: datetime,
    ) -> list[tuple[Story, int]]:
        statement = (
            select(Story, func.count(StoryView.id))
            .outerjoin(StoryView, StoryView.story_id == Story.id)
            .where(
                Story.owner_account_id == owner_account_id,
                Story.status == "active",
                Story.deleted_at.is_(None),
            )
            .group_by(Story.id)
            .order_by(Story.created_at.desc(), Story.id.desc())
        )
        if state == "active":
            statement = statement.where(Story.expires_at > now)
        elif state == "archived":
            statement = statement.where(Story.expires_at <= now)
        return [
            (story, int(count or 0))
            for story, count in (await session.execute(statement)).all()
        ]

    async def owner_id_by_public_id(
        self,
        session: AsyncSession,
        *,
        owner_type: str,
        public_id: str,
    ) -> int | None:
        model = BusinessProfile if owner_type == "business" else UserProfile
        value = await session.scalar(
            select(model.account_id)
            .join(Account, Account.id == model.account_id)
            .where(model.public_id == public_id, Account.status == "active")
        )
        return int(value) if value is not None else None

    async def profiles(
        self,
        session: AsyncSession,
        account_ids: set[int],
    ) -> dict[int, dict[str, object]]:
        if not account_ids:
            return {}
        result: dict[int, dict[str, object]] = {}
        for model, kind, avatar_field in (
            (UserProfile, "user", "avatar_object_key"),
            (BusinessProfile, "business", "logo_object_key"),
        ):
            rows = (
                await session.scalars(
                    select(model).where(model.account_id.in_(account_ids))
                )
            ).all()
            for profile in rows:
                result[int(profile.account_id)] = {
                    "kind": kind,
                    "public_id": profile.public_id,
                    "name": profile.name,
                    "latitude": profile.latitude,
                    "longitude": profile.longitude,
                    "avatar_object_key": getattr(profile, avatar_field),
                }
        return result

    async def followed_ids(
        self,
        session: AsyncSession,
        *,
        follower_account_id: int | None,
        target_ids: set[int],
    ) -> set[int]:
        if follower_account_id is None or not target_ids:
            return set()
        values = await session.scalars(
            select(ProfileFollow.target_account_id).where(
                ProfileFollow.follower_account_id == follower_account_id,
                ProfileFollow.target_account_id.in_(target_ids),
            )
        )
        return {int(value) for value in values.all()}

    async def same_person_account_ids(
        self,
        session: AsyncSession,
        account_id: int,
    ) -> set[int]:
        ids = {account_id}
        links = (
            await session.scalars(
                select(ProfileLink).where(
                    or_(
                        ProfileLink.user_account_id == account_id,
                        ProfileLink.business_account_id == account_id,
                    )
                )
            )
        ).all()
        for link in links:
            ids.add(int(link.user_account_id))
            ids.add(int(link.business_account_id))
        return ids

    async def record_view(
        self,
        session: AsyncSession,
        *,
        story_id: int,
        viewer_account_id: int,
        viewed_at: datetime,
    ) -> bool:
        statement = (
            postgresql_insert(StoryView)
            .values(
                story_id=story_id,
                viewer_account_id=viewer_account_id,
                viewed_at=viewed_at,
            )
            .on_conflict_do_nothing(
                constraint="uq_story_views_story_viewer",
            )
            .returning(StoryView.id)
        )
        return (await session.scalar(statement)) is not None

    async def viewers(
        self,
        session: AsyncSession,
        story_id: int,
    ) -> list[StoryView]:
        return list((await session.scalars(
            select(StoryView)
            .where(StoryView.story_id == story_id)
            .order_by(StoryView.viewed_at.desc())
        )).all())

    async def upsert_report(
        self,
        session: AsyncSession,
        *,
        story_id: int,
        reporter_account_id: int,
        reason: str,
        now: datetime,
    ) -> None:
        statement = (
            postgresql_insert(StoryReport)
            .values(
                story_id=story_id,
                reporter_account_id=reporter_account_id,
                reason=reason,
                status="new",
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_story_reports_story_reporter",
                set_={
                    "reason": reason,
                    "status": "new",
                    "created_at": now,
                    "updated_at": now,
                },
            )
        )
        await session.execute(statement)

    async def delete_story(self, session: AsyncSession, story_id: int) -> None:
        await session.execute(delete(Story).where(Story.id == story_id))
