"""`EducationManagementService` — mixin'lardan yig'iladi.

Meros tartibi muhim emas: mixin'lar bir-birining metodini qayta
e'lon qilmaydi, hammasi `EducationManagementServiceBase` dan oziqlanadi.
"""

from __future__ import annotations

from app.education.management.attendance import AttendanceMixin
from app.education.management.base import EducationManagementServiceBase
from app.education.management.groups import GroupsMixin
from app.education.management.payments import PaymentsMixin
from app.education.management.payroll import PayrollMixin
from app.education.management.students import StudentsMixin
from app.education.management.teachers import TeachersMixin


class EducationManagementService(
    GroupsMixin,
    StudentsMixin,
    AttendanceMixin,
    PaymentsMixin,
    TeachersMixin,
    PayrollMixin,
    EducationManagementServiceBase,
):
    """O'quv markazi kabineti uchun barcha amallar."""
