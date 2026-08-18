"""`QueueRepository` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.queues.repository_parts.base import QueueRepositoryBase
from app.queues.repository_parts.entries import EntriesMixin
from app.queues.repository_parts.listing import ListingMixin
from app.queues.repository_parts.providers import ProvidersMixin


class QueueRepository(
    ProvidersMixin,
    EntriesMixin,
    ListingMixin,
    QueueRepositoryBase,
):
    """Navbat jadvallariga barcha so'rovlar."""
