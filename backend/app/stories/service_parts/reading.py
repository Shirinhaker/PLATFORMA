"""Lenta, korish va koruvchilar."""

from __future__ import annotations

from typing import Any

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.stories.model import Story
from app.stories.schemas import (
    ManagedStoryRead,
    StoryGroup,
    StoryRead,
    StoryViewerRead,
    StoryViewResult,
)
from app.stories.service_parts.base import StoryServiceBase
from app.stories.service_parts.helpers import (
    _distance_km,
    rank_story_groups,
)


class ReadingMixin(StoryServiceBase):
    async def feed(
        self,
        *,
        account_id: int | None,
        account_type: AccountType | None,
        latitude: float | None,
        longitude: float | None,
    ) -> list[StoryGroup]:
        async with self._session_factory() as session:
            rows = await self._repository.feed_rows(
                session,
                viewer_account_id=account_id,
                now=self._now(),
            )
            owner_ids = {int(story.owner_account_id) for story, _ in rows}
            profiles = await self._repository.profiles(session, owner_ids)
            followed = await self._repository.followed_ids(
                session,
                follower_account_id=account_id,
                target_ids=owner_ids,
            )
            grouped: dict[int, list[tuple[Story, bool]]] = {}
            for story, viewed in rows:
                grouped.setdefault(int(story.owner_account_id), []).append(
                    (story, viewed)
                )
            result: list[dict[str, Any]] = []
            for owner_id, story_rows in grouped.items():
                profile = profiles.get(owner_id)
                if profile is None:
                    continue
                stories = [
                    self._story_read(story, profile, viewed=viewed)
                    for story, viewed in story_rows
                ]
                result.append(
                    {
                        "owner_type": profile["kind"],
                        "owner_public_id": self._public_id(profile, owner_id),
                        "name": str(profile["name"]),
                        "avatar_url": self._url(str(profile["avatar_object_key"])),
                        "is_own": bool(
                            account_id == owner_id and account_type is not None
                        ),
                        "is_followed": owner_id in followed,
                        "has_unseen": any(not story.viewed for story in stories),
                        "distance_km": _distance_km(
                            latitude,
                            longitude,
                            profile.get("latitude"),
                            profile.get("longitude"),
                        ),
                        "stories": stories,
                        "latest_story_at": max(story.created_at for story in stories),
                    }
                )
            ranked = rank_story_groups(result)
            for item in ranked:
                item.pop("latest_story_at", None)
            response = [StoryGroup.model_validate(item) for item in ranked]
            await session.rollback()
            return response

    async def owner_stories(
        self,
        *,
        owner_type: str,
        owner_public_id: str,
        viewer_account_id: int | None,
    ) -> list[StoryRead]:
        if owner_type not in {"user", "business"}:
            raise ApiError(400, "story_owner_type_invalid", "Profil turi noto‘g‘ri.")
        async with self._session_factory() as session:
            owner_id = await self._repository.owner_id_by_public_id(
                session,
                owner_type=owner_type,
                public_id=owner_public_id,
            )
            if owner_id is None:
                raise ApiError(404, "story_owner_not_found", "Profil topilmadi.")
            rows = await self._repository.owner_rows(
                session,
                owner_account_id=owner_id,
                viewer_account_id=viewer_account_id,
                now=self._now(),
            )
            profile = (await self._repository.profiles(session, {owner_id})).get(
                owner_id, {}
            )
            response = [
                self._story_read(story, profile, viewed=viewed)
                for story, viewed in rows
            ]
            await session.rollback()
            return response

    async def mine(
        self,
        *,
        account_id: int,
        state: str,
    ) -> list[ManagedStoryRead]:
        if state not in {"active", "archived", "all"}:
            raise ApiError(
                400,
                "story_state_invalid",
                "Holat active, archived yoki all bo‘lishi kerak.",
            )
        async with self._session_factory() as session:
            rows = await self._repository.managed_rows(
                session,
                owner_account_id=account_id,
                state=state,
                now=self._now(),
            )
            profile = (await self._repository.profiles(session, {account_id})).get(
                account_id, {}
            )
            response = [
                ManagedStoryRead(
                    **self._story_read(story, profile, viewed=False).model_dump(),
                    view_count=view_count,
                )
                for story, view_count in rows
            ]
            await session.rollback()
            return response

    async def view(self, *, story_id: int, account_id: int) -> StoryViewResult:
        async with self._session_factory() as session:
            story = await self._repository.active_story(session, story_id, self._now())
            if story is None:
                raise ApiError(
                    404,
                    "story_not_found",
                    "Istoriya topilmadi yoki muddati tugagan.",
                )
            same_person = await self._repository.same_person_account_ids(
                session, account_id
            )
            if int(story.owner_account_id) in same_person:
                await session.rollback()
                return StoryViewResult(counted=False)
            counted = await self._repository.record_view(
                session,
                story_id=story_id,
                viewer_account_id=account_id,
                viewed_at=self._now(),
            )
            await session.commit()
            return StoryViewResult(counted=counted)

    async def viewers(
        self,
        *,
        story_id: int,
        owner_account_id: int,
    ) -> list[StoryViewerRead]:
        async with self._session_factory() as session:
            story = await self._repository.managed_story(
                session,
                story_id=story_id,
                owner_account_id=owner_account_id,
            )
            if story is None:
                raise ApiError(
                    403,
                    "story_owner_required",
                    "Ko‘rganlar ro‘yxati faqat istoriya egasiga ochiq.",
                )
            rows = await self._repository.viewers(session, story_id)
            ids = {int(row.viewer_account_id) for row in rows}
            profiles = await self._repository.profiles(session, ids)
            response = [
                StoryViewerRead(
                    account_public_id=self._public_id(
                        profiles.get(int(row.viewer_account_id), {}),
                        int(row.viewer_account_id),
                    ),
                    name=str(
                        profiles.get(int(row.viewer_account_id), {}).get(
                            "name", "Profil"
                        )
                    ),
                    viewed_at=row.viewed_at,
                )
                for row in rows
            ]
            await session.rollback()
            return response
