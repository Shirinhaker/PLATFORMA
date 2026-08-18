"""Story joylash, ochirish va shikoyat."""

from __future__ import annotations

import contextlib
from datetime import timedelta

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.media.storage import UploadRejected
from app.stories.model import Story
from app.stories.processor import (
    MAX_ACTIVE_STORIES,
    STORY_TTL_SECONDS,
    StoryValidationError,
)
from app.stories.schemas import (
    StoryCreate,
    StoryCreated,
)
from app.stories.service_parts.base import StoryServiceBase


class PublishingMixin(StoryServiceBase):
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
            with contextlib.suppress(Exception):
                self._storage.delete_object(body.object_key)
            if isinstance(exc, (StoryValidationError, UploadRejected)):
                raise ApiError(400, "story_upload_rejected", str(exc)) from None
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
                profile = (await self._repository.profiles(session, {account_id})).get(
                    account_id
                )
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
                    with contextlib.suppress(Exception):
                        self._storage.delete_object(key)
            if isinstance(exc, ApiError):
                raise
            raise ApiError(
                500,
                "story_activation_failed",
                "Istoriya saqlanmadi. Qayta urinib ko‘ring.",
            ) from exc

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
                with contextlib.suppress(Exception):
                    self._storage.delete_object(key)

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
