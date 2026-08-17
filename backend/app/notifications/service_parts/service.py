"""`NotificationService` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.notifications.service_parts.base import NotificationServiceBase
from app.notifications.service_parts.devices import DevicesMixin
from app.notifications.service_parts.events import EventsMixin
from app.notifications.service_parts.inbox import InboxMixin
from app.notifications.service_parts.preferences import PreferencesMixin


class NotificationService(
    InboxMixin,
    PreferencesMixin,
    DevicesMixin,
    EventsMixin,
    NotificationServiceBase,
):
    """Bildirishnomalar, sozlamalar va push qurilmalari."""
