"""Umumiy asos: maydon qiymatlari va guruh tarixi."""

from __future__ import annotations

from app.education.repository import EducationEnrollmentRepository


class EducationCabinetServiceBase:
    def __init__(
        self,
        *,
        repository: EducationEnrollmentRepository | None = None,
    ) -> None:
        self._repository = repository or EducationEnrollmentRepository()
