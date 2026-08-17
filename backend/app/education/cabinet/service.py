"""`EducationCabinetService` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.education.cabinet.base import EducationCabinetServiceBase
from app.education.cabinet.groups import GroupsMixin
from app.education.cabinet.students import StudentsMixin


class EducationCabinetService(
    GroupsMixin,
    StudentsMixin,
    EducationCabinetServiceBase,
):
    """O'quv kabinetidagi guruh va o'quvchi amallari."""
