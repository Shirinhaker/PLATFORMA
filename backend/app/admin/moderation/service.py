"""`AdminModerationService` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.admin.moderation.accounts import AccountsMixin
from app.admin.moderation.base import AdminModerationServiceBase
from app.admin.moderation.content import ContentMixin
from app.admin.moderation.restrictions import RestrictionsMixin


class AdminModerationService(
    AccountsMixin,
    RestrictionsMixin,
    ContentMixin,
    AdminModerationServiceBase,
):
    """Admin moderatsiyasi: akkaunt, cheklov, kontent."""
