"""Umumiy asos: story javobi, media manzili, holat."""

from __future__ import annotations

from datetime import UTC, datetime

from app.accounts.model import AccountType
from app.media.storage import R2Storage
from app.public_ids import build_profile_public_id
from app.stories.model import Story
from app.stories.processor import (
    StoryMediaProcessor,
)
from app.stories.repository import StoryRepository
from app.stories.schemas import (
    StoryRead,
)
from app.stories.service_parts.helpers import (
    NowProvider,
    SessionFactory,
)


class StoryServiceBase:
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
            profile.get("public_id") or build_profile_public_id(kind, account_id)
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
