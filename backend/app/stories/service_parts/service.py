"""`StoryService` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.stories.service_parts.base import StoryServiceBase
from app.stories.service_parts.publishing import PublishingMixin
from app.stories.service_parts.reading import ReadingMixin


class StoryService(
    PublishingMixin,
    ReadingMixin,
    StoryServiceBase,
):
    """Storieslarni joylash va ko'rish."""
