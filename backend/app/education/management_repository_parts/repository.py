"""`EducationManagementRepository` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.education.management_repository_parts.attendance import AttendanceMixin
from app.education.management_repository_parts.base import (
    EducationManagementRepositoryBase,
)
from app.education.management_repository_parts.cash import CashMixin
from app.education.management_repository_parts.groups import GroupsMixin
from app.education.management_repository_parts.payments import PaymentsMixin
from app.education.management_repository_parts.payroll import PayrollMixin
from app.education.management_repository_parts.teachers import TeachersMixin


class EducationManagementRepository(
    GroupsMixin,
    AttendanceMixin,
    PaymentsMixin,
    TeachersMixin,
    PayrollMixin,
    CashMixin,
    EducationManagementRepositoryBase,
):
    """O'quv markazi boshqaruvi uchun barcha so'rovlar."""
