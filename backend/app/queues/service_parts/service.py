"""`QueueService` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.queues.service_parts.availability import AvailabilityMixin
from app.queues.service_parts.base import QueueServiceBase
from app.queues.service_parts.booking import BookingMixin
from app.queues.service_parts.lifecycle import LifecycleMixin
from app.queues.service_parts.listing import ListingMixin
from app.queues.service_parts.providers import ProvidersMixin


class QueueService(
    ProvidersMixin,
    AvailabilityMixin,
    BookingMixin,
    ListingMixin,
    LifecycleMixin,
    QueueServiceBase,
):
    """Navbat bo'yicha barcha amallar."""
