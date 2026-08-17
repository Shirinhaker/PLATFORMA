"""`BusinessOnlineService` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.business_online.service_parts.actions import ActionsMixin
from app.business_online.service_parts.base import BusinessOnlineServiceBase
from app.business_online.service_parts.crud import CrudMixin
from app.business_online.service_parts.education import EducationMixin
from app.business_online.service_parts.notifications import NotificationsMixin


class BusinessOnlineService(
    CrudMixin,
    ActionsMixin,
    EducationMixin,
    NotificationsMixin,
    BusinessOnlineServiceBase,
):
    """Kabinet resurslari bo'yicha barcha amallar."""
