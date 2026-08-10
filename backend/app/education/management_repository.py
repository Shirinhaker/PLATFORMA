"""Ta'lim boshqaruvi uchun tenant-scoped relatsion so'rovlar."""

from __future__ import annotations

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cash_register.model import CashReceipt, CashReceiptLine
from app.education.model import (
    EducationAttendance,
    EducationGroup,
    EducationPayment,
    EducationStudent,
    EducationTeacher,
    EducationTeacherPayment,
)
from app.expenses.model import Expense
from app.profiles.model import BusinessProfile


class EducationManagementRepository:
    async def profile(
        self,
        session: AsyncSession,
        business_account_id: int,
    ) -> BusinessProfile | None:
        return await session.get(BusinessProfile, business_account_id)

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
        return (await session.execute(
            select(EducationGroup, student_count.label("student_count"))
            .where(
                EducationGroup.business_account_id == business_account_id,
                EducationGroup.status == "active",
            )
            .order_by(EducationGroup.id.desc())
        )).all()

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

    async def attendance_for_day(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        group_id: int,
        lesson_date: str,
    ):
        return (await session.execute(
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
        )).all()

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
        return list((await session.scalars(
            select(EducationAttendance).where(
                EducationAttendance.business_account_id == business_account_id,
                EducationAttendance.group_id == group_id,
                EducationAttendance.lesson_date == lesson_date,
            )
        )).all())

    async def payment_totals(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        student_ids: list[int],
        minimum_month: str = "",
    ):
        if not student_ids:
            return []
        statement = (
            select(
                EducationPayment.student_id,
                EducationPayment.payment_month,
                func.coalesce(func.sum(EducationPayment.amount), 0),
            )
            .where(
                EducationPayment.business_account_id == business_account_id,
                EducationPayment.student_id.in_(student_ids),
                EducationPayment.voided_at.is_(None),
            )
            .group_by(EducationPayment.student_id, EducationPayment.payment_month)
        )
        if minimum_month:
            statement = statement.where(
                EducationPayment.payment_month >= minimum_month
            )
        return (await session.execute(statement)).all()

    async def active_payments(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        student_ids: list[int],
        minimum_month: str = "",
    ) -> list[EducationPayment]:
        if not student_ids:
            return []
        statement = select(EducationPayment).where(
            EducationPayment.business_account_id == business_account_id,
            EducationPayment.student_id.in_(student_ids),
            EducationPayment.voided_at.is_(None),
        )
        if minimum_month:
            statement = statement.where(
                EducationPayment.payment_month >= minimum_month
            )
        return list((await session.scalars(statement)).all())

    async def payment_history(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        payment_month: str,
    ):
        return (await session.execute(
            select(EducationPayment, EducationStudent.full_name)
            .outerjoin(
                EducationStudent,
                (EducationStudent.id == EducationPayment.student_id)
                & (
                    EducationStudent.business_account_id
                    == EducationPayment.business_account_id
                ),
            )
            .where(
                EducationPayment.business_account_id == business_account_id,
                EducationPayment.payment_month == payment_month,
            )
            .order_by(EducationPayment.id.desc())
            .limit(300)
        )).all()

    async def payment(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        payment_id: int,
        lock: bool = False,
    ) -> EducationPayment | None:
        statement = select(EducationPayment).where(
            EducationPayment.id == payment_id,
            EducationPayment.business_account_id == business_account_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

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
        return (await session.execute(
            select(EducationTeacher, group_count.label("group_count"))
            .where(
                EducationTeacher.business_account_id == business_account_id,
                EducationTeacher.status == "active",
            )
            .order_by(func.lower(EducationTeacher.full_name), EducationTeacher.id)
        )).all()

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
        return (await session.execute(
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
        )).all()

    async def teacher_payment_totals(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        payment_month: str,
    ):
        return (await session.execute(
            select(
                EducationTeacherPayment.teacher_id,
                func.coalesce(func.sum(EducationTeacherPayment.amount), 0),
            )
            .where(
                EducationTeacherPayment.business_account_id
                == business_account_id,
                EducationTeacherPayment.payment_month == payment_month,
            )
            .group_by(EducationTeacherPayment.teacher_id)
        )).all()

    async def teacher_payment_history(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        payment_month: str,
    ):
        return (await session.execute(
            select(EducationTeacherPayment, EducationTeacher.full_name)
            .outerjoin(
                EducationTeacher,
                (EducationTeacher.id == EducationTeacherPayment.teacher_id)
                & (
                    EducationTeacher.business_account_id
                    == EducationTeacherPayment.business_account_id
                ),
            )
            .where(
                EducationTeacherPayment.business_account_id
                == business_account_id,
                EducationTeacherPayment.payment_month == payment_month,
            )
            .order_by(EducationTeacherPayment.id.desc())
            .limit(300)
        )).all()

    async def teacher_payment(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        payment_id: int,
        lock: bool = False,
    ) -> EducationTeacherPayment | None:
        statement = select(EducationTeacherPayment).where(
            EducationTeacherPayment.id == payment_id,
            EducationTeacherPayment.business_account_id == business_account_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def salary_expense(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        expense_id: int,
    ) -> Expense | None:
        return await session.scalar(
            select(Expense).where(
                Expense.id == expense_id,
                Expense.business_account_id == business_account_id,
                Expense.source == "education_salary",
            )
        )

    async def clear_cash_receipt_lines(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        receipt_id: int,
    ) -> None:
        await session.execute(
            delete(CashReceiptLine).where(
                CashReceiptLine.business_account_id == business_account_id,
                CashReceiptLine.receipt_id == receipt_id,
            )
        )

    async def cash_receipt(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        receipt_id: int,
        lock: bool = False,
    ) -> CashReceipt | None:
        statement = select(CashReceipt).where(
            CashReceipt.id == receipt_id,
            CashReceipt.business_account_id == business_account_id,
            CashReceipt.source == "education",
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)
