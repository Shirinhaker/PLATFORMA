from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.education.model import (
    CourseEnrollment,
    EducationAttendance,
    EducationGroup,
    EducationPayment,
    EducationStudent,
    EducationTeacher,
    EducationTeacherPayment,
)
from app.expenses.model import Expense
from app.profiles.model import BusinessProfile


class EducationStatisticsRepository:
    async def business_direction(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
    ) -> str | None:
        return await session.scalar(
            select(BusinessProfile.direction).where(
                BusinessProfile.account_id == business_account_id
            )
        )

    async def process_summary(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        start_date: str,
        end_date: str,
        start_epoch: int,
        end_epoch: int,
    ):
        active_students = (
            select(func.count(EducationStudent.id))
            .where(
                EducationStudent.business_account_id == business_account_id,
                EducationStudent.status == "active",
            )
            .scalar_subquery()
        )
        active_groups = (
            select(func.count(EducationGroup.id))
            .where(
                EducationGroup.business_account_id == business_account_id,
                EducationGroup.status == "active",
            )
            .scalar_subquery()
        )
        new_enrollments = (
            select(func.count(CourseEnrollment.id))
            .where(
                CourseEnrollment.business_account_id == business_account_id,
                CourseEnrollment.created_at >= start_epoch,
                CourseEnrollment.created_at < end_epoch,
            )
            .scalar_subquery()
        )
        attendance_total = (
            select(func.count(EducationAttendance.id))
            .where(
                EducationAttendance.business_account_id == business_account_id,
                EducationAttendance.lesson_date >= start_date,
                EducationAttendance.lesson_date <= end_date,
            )
            .scalar_subquery()
        )
        attendance_present = (
            select(func.count(EducationAttendance.id))
            .where(
                EducationAttendance.business_account_id == business_account_id,
                EducationAttendance.lesson_date >= start_date,
                EducationAttendance.lesson_date <= end_date,
                EducationAttendance.attendance_status.in_(("present", "late")),
            )
            .scalar_subquery()
        )
        return (await session.execute(select(
            active_students.label("active_students"),
            active_groups.label("active_groups"),
            new_enrollments.label("new_enrollments"),
            attendance_total.label("attendance_total"),
            attendance_present.label("attendance_present"),
        ))).one()

    async def group_rows(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        start_date: str,
        end_date: str,
    ):
        student_counts = (
            select(
                EducationStudent.group_id.label("group_id"),
                func.count(EducationStudent.id).label("active_students"),
            )
            .where(
                EducationStudent.business_account_id == business_account_id,
                EducationStudent.status == "active",
                EducationStudent.group_id.is_not(None),
            )
            .group_by(EducationStudent.group_id)
            .subquery()
        )
        attendance_counts = (
            select(
                EducationAttendance.group_id.label("group_id"),
                func.count(EducationAttendance.id).label("attendance_total"),
                func.sum(case(
                    (
                        EducationAttendance.attendance_status.in_(
                            ("present", "late")
                        ),
                        1,
                    ),
                    else_=0,
                )).label("attendance_present"),
            )
            .where(
                EducationAttendance.business_account_id == business_account_id,
                EducationAttendance.lesson_date >= start_date,
                EducationAttendance.lesson_date <= end_date,
                EducationAttendance.group_id.is_not(None),
            )
            .group_by(EducationAttendance.group_id)
            .subquery()
        )
        return (await session.execute(
            select(
                EducationGroup.id,
                EducationGroup.name,
                func.coalesce(student_counts.c.active_students, 0).label(
                    "active_students"
                ),
                func.coalesce(attendance_counts.c.attendance_total, 0).label(
                    "attendance_total"
                ),
                func.coalesce(attendance_counts.c.attendance_present, 0).label(
                    "attendance_present"
                ),
            )
            .outerjoin(student_counts, student_counts.c.group_id == EducationGroup.id)
            .outerjoin(
                attendance_counts,
                attendance_counts.c.group_id == EducationGroup.id,
            )
            .where(
                EducationGroup.business_account_id == business_account_id,
                EducationGroup.status == "active",
            )
            .order_by(func.lower(EducationGroup.name), EducationGroup.id)
        )).all()

    async def active_students(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
    ):
        return (await session.execute(
            select(
                EducationStudent.id,
                EducationStudent.group_id,
                EducationStudent.monthly_fee,
                EducationStudent.joined_date,
                EducationGroup.billing_type,
                EducationGroup.package_lessons,
                EducationGroup.package_price,
            )
            .outerjoin(
                EducationGroup,
                and_(
                    EducationGroup.id == EducationStudent.group_id,
                    EducationGroup.business_account_id == business_account_id,
                ),
            )
            .where(
                EducationStudent.business_account_id == business_account_id,
                EducationStudent.status == "active",
            )
            .order_by(EducationStudent.id)
        )).all()

    async def attendance_billing_rows(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        start_date: str,
        end_date: str,
    ):
        month = func.substr(EducationAttendance.lesson_date, 1, 7)
        return (await session.execute(
            select(
                EducationAttendance.student_id,
                month.label("month"),
                func.count(EducationAttendance.id).label("lessons"),
            )
            .where(
                EducationAttendance.business_account_id == business_account_id,
                EducationAttendance.lesson_date >= start_date,
                EducationAttendance.lesson_date <= end_date,
                EducationAttendance.student_id.is_not(None),
                EducationAttendance.attendance_status.in_(
                    ("present", "late", "absent")
                ),
            )
            .group_by(EducationAttendance.student_id, month)
        )).all()

    async def student_payment_rows(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        start: datetime,
        end: datetime,
    ):
        return (await session.execute(
            select(
                EducationStudent.group_id,
                func.coalesce(func.sum(EducationPayment.amount), 0).label("amount"),
            )
            .select_from(EducationPayment)
            .join(
                EducationStudent,
                and_(
                    EducationStudent.id == EducationPayment.student_id,
                    EducationStudent.business_account_id == business_account_id,
                ),
            )
            .where(
                EducationPayment.business_account_id == business_account_id,
                EducationPayment.created_at >= start,
                EducationPayment.created_at < end,
                EducationPayment.voided_at.is_(None),
            )
            .group_by(EducationStudent.group_id)
        )).all()

    async def active_teachers(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
    ):
        return (await session.execute(
            select(
                EducationTeacher.id,
                EducationTeacher.salary_type,
                EducationTeacher.salary_amount,
                EducationTeacher.hired_date,
            )
            .where(
                EducationTeacher.business_account_id == business_account_id,
                EducationTeacher.status == "active",
            )
            .order_by(EducationTeacher.id)
        )).all()

    async def teacher_lesson_rows(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        start_date: str,
        end_date: str,
    ):
        distinct_lessons = (
            select(
                EducationGroup.teacher_id.label("teacher_id"),
                EducationAttendance.group_id.label("group_id"),
                EducationAttendance.lesson_date.label("lesson_date"),
            )
            .select_from(EducationAttendance)
            .join(
                EducationGroup,
                and_(
                    EducationGroup.id == EducationAttendance.group_id,
                    EducationGroup.business_account_id == business_account_id,
                ),
            )
            .where(
                EducationAttendance.business_account_id == business_account_id,
                EducationAttendance.lesson_date >= start_date,
                EducationAttendance.lesson_date <= end_date,
                EducationGroup.teacher_id.is_not(None),
            )
            .group_by(
                EducationGroup.teacher_id,
                EducationAttendance.group_id,
                EducationAttendance.lesson_date,
            )
            .subquery()
        )
        return (await session.execute(
            select(
                distinct_lessons.c.teacher_id,
                func.count().label("lessons"),
            ).group_by(distinct_lessons.c.teacher_id)
        )).all()

    async def teacher_paid(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        start: datetime,
        end: datetime,
    ) -> int:
        return int(await session.scalar(
            select(func.coalesce(func.sum(EducationTeacherPayment.amount), 0)).where(
                EducationTeacherPayment.business_account_id == business_account_id,
                EducationTeacherPayment.created_at >= start,
                EducationTeacherPayment.created_at < end,
            )
        ) or 0)

    async def other_expenses(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        start: datetime,
        end: datetime,
    ) -> int:
        return int(await session.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                Expense.business_account_id == business_account_id,
                Expense.created_at >= start,
                Expense.created_at < end,
                Expense.source != "education_salary",
            )
        ) or 0)
