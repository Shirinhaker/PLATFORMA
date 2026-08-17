"""`StaffService` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.staff.service_parts.access import AccessMixin
from app.staff.service_parts.attendance import AttendanceMixin
from app.staff.service_parts.base import StaffServiceBase
from app.staff.service_parts.members import MembersMixin
from app.staff.service_parts.sessions import SessionsMixin


class StaffService(
    MembersMixin,
    AccessMixin,
    AttendanceMixin,
    SessionsMixin,
    StaffServiceBase,
):
    """Xodimlar, huquqlar, davomat va seanslar."""
