"""`NotificationRepository` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.notifications.repository_parts.base import NotificationRepositoryBase
from app.notifications.repository_parts.devices import DevicesMixin
from app.notifications.repository_parts.inbox import InboxMixin
from app.notifications.repository_parts.preferences import PreferencesMixin


class NotificationRepository(
    InboxMixin,
    PreferencesMixin,
    DevicesMixin,
    NotificationRepositoryBase,
):
    """Bildirishnomalar, sozlamalar va push qurilmalari uchun so'rovlar."""
