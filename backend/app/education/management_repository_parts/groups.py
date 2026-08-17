"""Guruhlar va o'quvchilar, guruh tarixi bilan."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.education.management_repository_parts.base import (
    EducationManagementRepositoryBase,
)
from app.education.model import (
    EducationGroup,
    EducationStudent,
    EducationStudentGroupHistory,
)


class GroupsMixin(EducationManagementRepositoryBase):
    async def active_groups(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
    ):
        student_count = (
            select(func.count(EducationStudent.id))
            .where(
                EducationStudent.business_account_id == business_account_id,
                EducationStudent.group_id == EducationGroup.id,
                EducationStudent.status == "active",
            )
            .correlate(EducationGroup)
            .scalar_subquery()
        )
        return (
            await session.execute(
                select(EducationGroup, student_count.label("student_count"))
                .where(
                    EducationGroup.business_account_id == business_account_id,
                    EducationGroup.status == "active",
                )
                .order_by(EducationGroup.id.desc())
            )
        ).all()

    async def active_group(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        group_id: int,
        lock: bool = False,
    ) -> EducationGroup | None:
        statement = select(EducationGroup).where(
            EducationGroup.id == group_id,
            EducationGroup.business_account_id == business_account_id,
            EducationGroup.status == "active",
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def active_students_with_groups(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        group_id: int = 0,
    ):
        statement = (
            select(EducationStudent, EducationGroup)
            .outerjoin(
                EducationGroup,
                (EducationGroup.id == EducationStudent.group_id)
                & (
                    EducationGroup.business_account_id
                    == EducationStudent.business_account_id
                ),
            )
            .where(
                EducationStudent.business_account_id == business_account_id,
                EducationStudent.status == "active",
            )
            .order_by(func.lower(EducationStudent.full_name), EducationStudent.id)
        )
        if group_id > 0:
            statement = statement.where(EducationStudent.group_id == group_id)
        return (await session.execute(statement)).all()

    async def active_student(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        student_id: int,
        lock: bool = False,
    ) -> EducationStudent | None:
        statement = select(EducationStudent).where(
            EducationStudent.id == student_id,
            EducationStudent.business_account_id == business_account_id,
            EducationStudent.status == "active",
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def student_group_history(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        student_id: int,
    ):
        return (
            await session.execute(
                select(EducationStudentGroupHistory, EducationGroup.name)
                .outerjoin(
                    EducationGroup,
                    (EducationGroup.id == EducationStudentGroupHistory.group_id)
                    & (
                        EducationGroup.business_account_id
                        == EducationStudentGroupHistory.business_account_id
                    ),
                )
                .where(
                    EducationStudentGroupHistory.business_account_id
                    == business_account_id,
                    EducationStudentGroupHistory.student_id == student_id,
                )
                .order_by(
                    EducationStudentGroupHistory.started_date.desc(),
                    EducationStudentGroupHistory.id.desc(),
                )
            )
        ).all()
