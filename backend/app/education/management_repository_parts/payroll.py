"""Oylik to'lovlari va xarajat yozuvi."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.education.management_repository_parts.base import (
    EducationManagementRepositoryBase,
)
from app.education.model import (
    EducationTeacher,
    EducationTeacherPayment,
)
from app.expenses.model import Expense


class PayrollMixin(EducationManagementRepositoryBase):
    async def teacher_payment_totals(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        payment_month: str,
    ):
        return (
            await session.execute(
                select(
                    EducationTeacherPayment.teacher_id,
                    func.coalesce(func.sum(EducationTeacherPayment.amount), 0),
                )
                .where(
                    EducationTeacherPayment.business_account_id == business_account_id,
                    EducationTeacherPayment.payment_month == payment_month,
                )
                .group_by(EducationTeacherPayment.teacher_id)
            )
        ).all()

    async def teacher_payment_history(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        payment_month: str,
    ):
        return (
            await session.execute(
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
                    EducationTeacherPayment.business_account_id == business_account_id,
                    EducationTeacherPayment.payment_month == payment_month,
                )
                .order_by(EducationTeacherPayment.id.desc())
                .limit(300)
            )
        ).all()

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
