"""Davomat yozuvlari."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.education.management_repository_parts.base import (
    EducationManagementRepositoryBase,
)
from app.education.model import (
    EducationAttendance,
    EducationStudent,
)


class AttendanceMixin(EducationManagementRepositoryBase):
    async def attendance_for_day(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        group_id: int,
        lesson_date: str,
    ):
        return (
            await session.execute(
                select(EducationStudent, EducationAttendance)
                .outerjoin(
                    EducationAttendance,
                    (EducationAttendance.business_account_id == business_account_id)
                    & (EducationAttendance.group_id == group_id)
                    & (EducationAttendance.student_id == EducationStudent.id)
                    & (EducationAttendance.lesson_date == lesson_date),
                )
                .where(
                    EducationStudent.business_account_id == business_account_id,
                    EducationStudent.group_id == group_id,
                    EducationStudent.status == "active",
                )
                .order_by(func.lower(EducationStudent.full_name), EducationStudent.id)
            )
        ).all()

    async def attendance_rows(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        student_ids: list[int],
        start_date: str,
        month: str = "",
    ) -> list[EducationAttendance]:
        if not student_ids:
            return []
        statement = select(EducationAttendance).where(
            EducationAttendance.business_account_id == business_account_id,
            EducationAttendance.student_id.in_(student_ids),
            EducationAttendance.lesson_date >= start_date,
        )
        if month:
            statement = statement.where(
                EducationAttendance.lesson_date.like(f"{month}-%")
            )
        return list((await session.scalars(statement)).all())

    async def existing_attendance(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        group_id: int,
        lesson_date: str,
    ) -> list[EducationAttendance]:
        return list(
            (
                await session.scalars(
                    select(EducationAttendance).where(
                        EducationAttendance.business_account_id == business_account_id,
                        EducationAttendance.group_id == group_id,
                        EducationAttendance.lesson_date == lesson_date,
                    )
                )
            ).all()
        )
