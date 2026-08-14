from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from app.accounts.model import AccountType
from app.outbox.model import OutboxEvent
from app.stories.model import Story
from app.stories.processor import ProcessedStoryMedia
from app.stories.schemas import StoryCreate
from app.stories.service import StoryService


class StorySession:
    def __init__(self, story: Story | None = None) -> None:
        self.story = story
        self.added: list[object] = []
        self.commits = 0

    def add(self, value: object) -> None:
        self.added.append(value)
        if isinstance(value, Story):
            value.id = 31
            self.story = value
        elif isinstance(value, OutboxEvent):
            value.id = 41

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def get(self, model, key, **_kwargs):
        if model is Story and self.story is not None and key == self.story.id:
            return self.story
        return None


class StoryRepositoryStub:
    async def lock_owner(self, _session, _account_id: int) -> None:
        return None

    async def active_count(self, _session, *, owner_account_id: int, now) -> int:
        return 0


class StorageStub:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete_object(self, object_key: str) -> None:
        self.deleted.append(object_key)


class ProcessorStub:
    async def process(self, **_kwargs) -> ProcessedStoryMedia:
        return ProcessedStoryMedia(
            media_type="video",
            media_object_key="private/business/7/story_video_processed/out.mp4",
            thumbnail_object_key="private/business/7/story_thumbnail/out.jpg",
            mime_type="video/mp4",
            caption="Sinov",
            duration_seconds=12.5,
        )


def sessions_for(session: StorySession):
    @asynccontextmanager
    async def factory():
        yield session

    return factory


async def test_story_create_only_enqueues_processing_job() -> None:
    session = StorySession()
    storage = StorageStub()
    service = StoryService(
        sessions_for(session),
        storage,
        repository=StoryRepositoryStub(),
        processor=ProcessorStub(),
        now_provider=lambda: datetime(2026, 8, 14, tzinfo=UTC),
    )

    created = await service.create(
        account_id=7,
        account_type=AccountType.BUSINESS,
        staff_id=None,
        body=StoryCreate(
            object_key="private/business/7/story_video/source.mp4",
            content_type="video/mp4",
            size_bytes=1024,
            caption=" Sinov ",
        ),
    )

    story = next(value for value in session.added if isinstance(value, Story))
    event = next(value for value in session.added if isinstance(value, OutboxEvent))
    assert created.story_id == 31
    assert created.status == "processing"
    assert story.status == "processing"
    assert story.media_object_key == ""
    assert event.topic == "story.media.process"
    assert event.payload == {"story_id": 31, "size_bytes": 1024}
    assert session.commits == 1
    assert storage.deleted == []


async def test_story_worker_activates_then_deletes_video_source() -> None:
    source = "private/business/7/story_video/source.mp4"
    now = datetime(2026, 8, 14, tzinfo=UTC)
    story = Story(
        id=31,
        owner_type="business",
        owner_account_id=7,
        created_by_account_id=7,
        created_by_staff_id=None,
        media_type="video",
        media_object_key="",
        thumbnail_object_key="",
        source_object_key=source,
        mime_type="video/mp4",
        caption="Sinov",
        duration_seconds=0,
        status="processing",
        legacy_source_id=None,
        migration_run_id=None,
        created_at=now,
        expires_at=now + timedelta(days=1),
        deleted_at=None,
    )
    session = StorySession(story)
    storage = StorageStub()
    service = StoryService(
        sessions_for(session),
        storage,
        processor=ProcessorStub(),
    )

    await service.process_pending(31, 1024)

    assert story.status == "active"
    assert story.source_object_key == ""
    assert story.media_object_key.endswith("/out.mp4")
    assert story.thumbnail_object_key.endswith("/out.jpg")
    assert storage.deleted == [source]
