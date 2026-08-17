"""O'qituvchilar va ularning darslari."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.education.management_repository_parts.base import (
    EducationManagementRepositoryBase,
)
from app.education.model import (
    EducationAttendance,
    EducationGroup,
    EducationTeacher,
)


class TeachersMixin(EducationManagementRepositoryBase):
    async def active_teachers(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
    ):
        group_count = (
            select(func.count(EducationGroup.id))
            .where(
                EducationGroup.business_account_id == business_account_id,
                EducationGroup.teacher_id == EducationTeacher.id,
                EducationGroup.status == "active",
            )
            .correlate(EducationTeacher)
            .scalar_subquery()
        )
        return (
            await session.execute(
                select(EducationTeacher, group_count.label("group_count"))
                .where(
                    EducationTeacher.business_account_id == business_account_id,
                    EducationTeacher.status == "active",
                )
                .order_by(func.lower(EducationTeacher.full_name), EducationTeacher.id)
            )
        ).all()

    async def active_teacher(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        teacher_id: int,
        lock: bool = False,
    ) -> EducationTeacher | None:
        statement = select(EducationTeacher).where(
            EducationTeacher.id == teacher_id,
            EducationTeacher.business_account_id == business_account_id,
            EducationTeacher.status == "active",
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def update_teacher_snapshot(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        teacher_id: int,
        full_name: str,
    ) -> None:
        await session.execute(
            update(EducationGroup)
            .where(
                EducationGroup.business_account_id == business_account_id,
                EducationGroup.teacher_id == teacher_id,
            )
            .values(teacher_name=full_name)
        )

    async def unlink_teacher(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        teacher_id: int,
    ) -> None:
        await session.execute(
            update(EducationGroup)
            .where(
                EducationGroup.business_account_id == business_account_id,
                EducationGroup.teacher_id == teacher_id,
            )
            .values(teacher_id=None)
        )

    async def teacher_lesson_pairs(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        payment_month: str,
    ):
        return (
            await session.execute(
                select(
                    EducationGroup.teacher_id,
                    EducationAttendance.group_id,
                    EducationAttendance.lesson_date,
                )
                .join(
                    EducationGroup,
                    (EducationGroup.id == EducationAttendance.group_id)
                    & (
                        EducationGroup.business_account_id
                        == EducationAttendance.business_account_id
                    ),
                )
                .where(
                    EducationAttendance.business_account_id == business_account_id,
                    EducationAttendance.lesson_date.like(f"{payment_month}-%"),
                    EducationGroup.teacher_id.is_not(None),
                )
                .distinct()
            )
        ).all()
