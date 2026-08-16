"""Umumiy asos: bog'liqliklar va huquq tekshiruvlari.

Barcha mixin'lar shundan meros oladi, ya'ni `self._repo` kabi
maydonlar bir joyda e'lon qilinadi va tur tekshiruvi ishlaydi.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.cash_register.repository import CashRegisterRepository
from app.core.errors import ApiError
from app.education.cabinet_service import EducationCabinetService
from app.education.management.helpers import (
    EDUCATION_DIRECTIONS,
    NowProvider,
    SessionFactory,
)
from app.education.management_repository import EducationManagementRepository
from app.education.repository import EducationEnrollmentRepository
from app.education.schemas import (
    EducationGroupRead,
)


class EducationManagementServiceBase:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: EducationManagementRepository | None = None,
        enrollment_repository: EducationEnrollmentRepository | None = None,
        cash_repository: CashRegisterRepository | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or EducationManagementRepository()
        self._education = enrollment_repository or EducationEnrollmentRepository()
        self._cabinet = EducationCabinetService(repository=self._education)
        self._cash = cash_repository or CashRegisterRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def _groups_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        profile,
    ) -> list[EducationGroupRead]:
        rows = await self._repository.active_groups(
            session,
            business_account_id=business_account_id,
        )
        catalog = await self._education.catalog_rows(session, profile)
        course_names = {
            str(row.get("id")): str(row.get("name") or "")
            for row in catalog
            if isinstance(row, dict)
        }
        return [
            EducationGroupRead(
                id=group.id,
                course_item_id=group.course_item_id,
                course_name=course_names.get(str(group.course_item_id or ""), ""),
                name=group.name,
                teacher_id=group.teacher_id,
                teacher_name=group.teacher_name,
                room_name=group.room_name,
                capacity=group.capacity,
                weekdays=group.weekdays,
                lesson_from=group.lesson_from,
                lesson_to=group.lesson_to,
                start_date=group.start_date,
                end_date=group.end_date,
                billing_type=(
                    "attendance" if group.billing_type == "attendance" else "monthly"
                ),
                package_lessons=group.package_lessons,
                package_price=group.package_price,
                student_count=int(student_count or 0),
            )
            for group, student_count in rows
        ]

    async def _require_scope(
        self,
        session: AsyncSession,
        business_account_id: int,
    ):
        profile = await self._repository.profile(session, business_account_id)
        if profile is None:
            raise ApiError(
                404, "business_profile_not_found", "Biznes profil topilmadi."
            )
        if profile.direction not in EDUCATION_DIRECTIONS:
            raise ApiError(
                403,
                "education_direction_required",
                "Bu bo'lim faqat Ta'lim faoliyati yo'nalishi uchun.",
            )
        return profile

    @staticmethod
    def _require_permission(
        permissions: tuple[str, ...] | None,
        required: str,
    ) -> None:
        if permissions is not None and required not in permissions:
            raise ApiError(
                403,
                "staff_permission_required",
                "Bu bo'limga vakolatingiz yo'q.",
            )

    @staticmethod
    def _require_any_education(permissions: tuple[str, ...] | None) -> None:
        if permissions is None:
            return
        if not any(value.startswith("education_") for value in permissions):
            raise ApiError(
                403,
                "staff_permission_required",
                "Bu bo'limga vakolatingiz yo'q.",
            )

    @staticmethod
    def _require_owner(
        permissions: tuple[str, ...] | None,
        action: str,
    ) -> None:
        if permissions is not None:
            raise ApiError(
                403,
                "business_owner_required",
                f"{action} faqat biznes egasi uchun.",
            )
