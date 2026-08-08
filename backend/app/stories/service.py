from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
import math
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.media.storage import R2Storage, UploadRejected
from app.public_ids import build_profile_public_id
from app.stories.model import Story
from app.stories.processor import (
    MAX_ACTIVE_STORIES,
    STORY_TTL_SECONDS,
    StoryMediaProcessor,
    StoryValidationError,
)
from app.stories.repository import StoryRepository
from app.stories.schemas import (
    ManagedStoryRead,
    StoryCreate,
    StoryCreated,
    StoryGroup,
    StoryRead,
    StoryViewResult,
    StoryViewerRead,
)


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NowProvider = Callable[[], datetime]


def _timestamp(value: object) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def rank_story_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        groups,
        key=lambda item: (
            0 if item.get("is_own") else 1,
            0 if item.get("has_unseen") else 1,
            0 if item.get("is_followed") else 1,
            (
                float(item["distance_km"])
                if item.get("distance_km") is not None
                else 1_000_000
            ),
            -_timestamp(item.get("latest_story_at")),
        ),
    )


def _distance_km(
    latitude: float | None,
    longitude: float | None,
    target_latitude: float | None,
    target_longitude: float | None,
) -> float | None:
    if None in (latitude, longitude, target_latitude, target_longitude):
        return None
    lat1, lng1, lat2, lng2 = map(
        float,
        (latitude, longitude, target_latitude, target_longitude),
    )
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    value = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


class StoryService:
    def __init__(
        self,
        session_factory: SessionFactory,
        storage: R2Storage,
        *,
        repository: StoryRepository | None = None,
        processor: StoryMediaProcessor | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._repository = repository or StoryRepository()
        self._processor = processor or StoryMediaProcessor(storage)
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        staff_id: int | None,
        body: StoryCreate,
    ) -> StoryCreated:
        now = self._now()
        prefix = f"private/{account_type.value}/{account_id}/story_"
        if not body.object_key.startswith(prefix):
            raise ApiError(
                403,
                "story_media_forbidden",
                "Bu media obyekti akkauntga tegishli emas.",
            )
        async with self._session_factory() as session:
            await self._repository.lock_owner(session, account_id)
            count = await self._repository.active_count(
                session,
                owner_account_id=account_id,
                now=now,
            )
            if count >= MAX_ACTIVE_STORIES:
                raise ApiError(
                    400,
                    "story_active_limit",
                    "Bir vaqtda ko‘pi bilan 10 ta faol istoriya joylash mumkin.",
                )
            guessed_type = (
                "video" if body.content_type.startswith("video/") else "image"
            )
            story = Story(
                owner_type=account_type.value,
                owner_account_id=account_id,
                created_by_account_id=account_id,
                created_by_staff_id=staff_id,
                media_type=guessed_type,
                media_object_key="",
                thumbnail_object_key="",
                source_object_key=body.object_key,
                mime_type=body.content_type,
                caption=body.caption.strip(),
                duration_seconds=0,
                status="processing",
                legacy_source_id=None,
                migration_run_id=None,
                created_at=now,
                expires_at=now + timedelta(seconds=STORY_TTL_SECONDS),
                deleted_at=None,
            )
            session.add(story)
            await session.commit()
            story_id = int(story.id)

        try:
            processed = await self._processor.process(
                owner_type=account_type,
                owner_id=account_id,
                object_key=body.object_key,
                claimed_type=body.content_type,
                claimed_size=body.size_bytes,
                caption=body.caption,
            )
        except Exception as exc:
            await self._mark_failed(story_id)
            try:
                self._storage.delete_object(body.object_key)
            except Exception:
                pass
            if isinstance(exc, (StoryValidationError, UploadRejected)):
                raise ApiError(
                    400, "story_upload_rejected", str(exc)
                ) from None
            raise ApiError(
                500,
                "story_processing_failed",
                "Istoriya joylanmadi. Qayta urinib ko‘ring.",
            ) from exc

        try:
            async with self._session_factory() as session:
                saved = await session.get(Story, story_id)
                if saved is None:
                    raise ApiError(404, "story_not_found", "Istoriya topilmadi.")
                saved.media_type = processed.media_type
                saved.media_object_key = processed.media_object_key
                saved.thumbnail_object_key = processed.thumbnail_object_key
                saved.source_object_key = ""
                saved.mime_type = processed.mime_type
                saved.caption = processed.caption
                saved.duration_seconds = processed.duration_seconds
                saved.status = "active"
                await session.commit()
                profile = (
                    await self._repository.profiles(session, {account_id})
                ).get(account_id)
                return StoryCreated(
                    story=self._story_read(saved, profile or {}, viewed=False)
                )
        except Exception as exc:
            await self._mark_failed(story_id)
            for key in {
                processed.media_object_key,
                processed.thumbnail_object_key,
            }:
                if key:
                    try:
                        self._storage.delete_object(key)
                    except Exception:
                        pass
            if isinstance(exc, ApiError):
                raise
            raise ApiError(
                500,
                "story_activation_failed",
                "Istoriya saqlanmadi. Qayta urinib ko‘ring.",
            ) from exc

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
                result.append({
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
                })
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

    async def delete(self, *, story_id: int, owner_account_id: int) -> None:
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
                    "Faqat o‘zingizning istoriyangizni o‘chira olasiz.",
                )
            keys = {
                story.media_object_key,
                story.thumbnail_object_key,
                story.source_object_key,
            }
            await self._repository.delete_story(session, story_id)
            await session.commit()
        for key in keys:
            if key:
                try:
                    self._storage.delete_object(key)
                except Exception:
                    pass

    async def report(
        self,
        *,
        story_id: int,
        reporter_account_id: int,
        reason: str,
    ) -> None:
        clean_reason = reason.strip()
        if not 10 <= len(clean_reason) <= 300:
            raise ApiError(
                400,
                "story_report_reason_invalid",
                "Shikoyat sababini 10–300 belgi bilan yozing.",
            )
        async with self._session_factory() as session:
            story = await self._repository.active_story(session, story_id, self._now())
            if story is None:
                raise ApiError(
                    404,
                    "story_not_found",
                    "Istoriya topilmadi yoki muddati tugagan.",
                )
            same_person = await self._repository.same_person_account_ids(
                session, reporter_account_id
            )
            if int(story.owner_account_id) in same_person:
                raise ApiError(
                    400,
                    "story_self_report_forbidden",
                    "O‘z istoriyangiz ustidan shikoyat yubora olmaysiz.",
                )
            await self._repository.upsert_report(
                session,
                story_id=story_id,
                reporter_account_id=reporter_account_id,
                reason=clean_reason,
                now=self._now(),
            )
            await session.commit()

    def _story_read(
        self,
        story: Story,
        profile: dict[str, object],
        *,
        viewed: bool,
    ) -> StoryRead:
        owner_id = int(story.owner_account_id)
        return StoryRead(
            id=int(story.id),
            owner_type=AccountType(story.owner_type),
            owner_public_id=self._public_id(profile, owner_id),
            media_type=story.media_type,
            media_url=self._url(story.media_object_key),
            thumbnail_url=self._url(
                story.thumbnail_object_key or story.media_object_key
            ),
            caption=story.caption,
            duration_seconds=float(story.duration_seconds or 0),
            created_at=story.created_at,
            expires_at=story.expires_at,
            viewed=viewed,
        )

    @staticmethod
    def _public_id(profile: dict[str, object], account_id: int) -> str:
        kind = str(profile.get("kind") or "user")
        return str(
            profile.get("public_id")
            or build_profile_public_id(kind, account_id)
        )

    def _url(self, object_key: str) -> str:
        return self._storage.create_download_url(object_key) if object_key else ""

    async def _mark_failed(self, story_id: int) -> None:
        async with self._session_factory() as session:
            failed = await session.get(Story, story_id)
            if failed is not None and failed.status == "processing":
                failed.status = "failed"
                await session.commit()

    def _now(self) -> datetime:
        value = self._now_provider()
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
