"""Oylik: hisoblash va to'lash."""

from __future__ import annotations

from app.core.errors import ApiError
from app.education.management.base import EducationManagementServiceBase
from app.education.management.helpers import (
    _month,
)
from app.education.model import (
    EducationTeacherPayment,
)
from app.education.schemas import (
    EducationPayrollCreate,
    EducationPayrollCreated,
    EducationPayrollHistoryRead,
    EducationPayrollRead,
    EducationPayrollTeacherRead,
)
from app.expenses.model import Expense


class PayrollMixin(EducationManagementServiceBase):
    async def payroll(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        payment_month: str,
    ) -> EducationPayrollRead:
        self._require_permission(permissions, "education_payroll")
        month = _month(payment_month, "Maosh oyini tanlang.")
        async with self._session_factory() as session:
            await self._require_scope(session, business_account_id)
            teachers = await self._repository.active_teachers(
                session,
                business_account_id=business_account_id,
            )
            lesson_rows = await self._repository.teacher_lesson_pairs(
                session,
                business_account_id=business_account_id,
                payment_month=month,
            )
            lesson_counts: dict[int, int] = {}
            for teacher_id, _group_id, _lesson_date in lesson_rows:
                if teacher_id is not None:
                    lesson_counts[int(teacher_id)] = (
                        lesson_counts.get(int(teacher_id), 0) + 1
                    )
            total_rows = await self._repository.teacher_payment_totals(
                session,
                business_account_id=business_account_id,
                payment_month=month,
            )
            paid = {
                int(teacher_id): int(amount or 0)
                for teacher_id, amount in total_rows
                if teacher_id is not None
            }
            output: list[EducationPayrollTeacherRead] = []
            for teacher, _group_count in teachers:
                lessons = lesson_counts.get(teacher.id, 0)
                expected = (
                    teacher.salary_amount
                    if teacher.salary_type == "monthly"
                    else lessons * teacher.salary_amount
                )
                paid_amount = paid.get(teacher.id, 0)
                output.append(
                    EducationPayrollTeacherRead(
                        id=teacher.id,
                        full_name=teacher.full_name,
                        salary_type=teacher.salary_type,
                        salary_amount=teacher.salary_amount,
                        lesson_count=lessons,
                        expected=expected,
                        paid=paid_amount,
                        debt=max(0, expected - paid_amount),
                    )
                )
            history_rows = await self._repository.teacher_payment_history(
                session,
                business_account_id=business_account_id,
                payment_month=month,
            )
            history = [
                EducationPayrollHistoryRead(
                    id=payment.id,
                    teacher_id=payment.teacher_id,
                    full_name=str(full_name or "O'qituvchi"),
                    payment_month=payment.payment_month,
                    amount=payment.amount,
                    pay_type=("karta" if payment.pay_type == "karta" else "naqd"),
                    note=payment.note,
                    created_at=payment.created_at,
                )
                for payment, full_name in history_rows
            ]
            await session.rollback()
            return EducationPayrollRead(
                payment_month=month,
                teachers=output,
                history=history,
            )

    async def create_payroll(
        self,
        *,
        business_account_id: int,
        actor_staff_id: int | None,
        permissions: tuple[str, ...] | None,
        body: EducationPayrollCreate,
    ) -> EducationPayrollCreated:
        self._require_permission(permissions, "education_payroll")
        month = _month(body.payment_month, "Maosh oyini tanlang.")
        now = self._now_provider()
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                teacher = await self._repository.active_teacher(
                    session,
                    business_account_id=business_account_id,
                    teacher_id=body.teacher_id,
                    lock=True,
                )
                if teacher is None:
                    raise ApiError(
                        404, "education_teacher_not_found", "O'qituvchi topilmadi."
                    )
                lesson_rows = await self._repository.teacher_lesson_pairs(
                    session,
                    business_account_id=business_account_id,
                    payment_month=month,
                )
                lessons = sum(
                    1
                    for teacher_id, _group, _day in lesson_rows
                    if teacher_id == teacher.id
                )
                expected = (
                    teacher.salary_amount
                    if teacher.salary_type == "monthly"
                    else lessons * teacher.salary_amount
                )
                totals = await self._repository.teacher_payment_totals(
                    session,
                    business_account_id=business_account_id,
                    payment_month=month,
                )
                already_paid = sum(
                    int(amount or 0)
                    for teacher_id, amount in totals
                    if teacher_id == teacher.id
                )
                if body.amount > max(0, expected - already_paid):
                    raise ApiError(
                        400,
                        "education_payroll_exceeds_debt",
                        "Summa qolgan maoshdan ko'p.",
                    )
                expense = Expense(
                    business_account_id=business_account_id,
                    legacy_source_id=None,
                    category="Maosh",
                    amount=body.amount,
                    note=(
                        f"{teacher.full_name} — {month}"
                        + (f": {body.note}" if body.note else "")
                    )[:200],
                    source="education_salary",
                    inventory_stock_move_id=None,
                    performed_by_staff_id=actor_staff_id,
                    actor_name_snapshot="",
                    created_at=now,
                )
                session.add(expense)
                await session.flush()
                payment = EducationTeacherPayment(
                    business_account_id=business_account_id,
                    legacy_source_id=None,
                    teacher_id=teacher.id,
                    legacy_teacher_id=teacher.legacy_source_id,
                    payment_month=month,
                    amount=body.amount,
                    pay_type=body.pay_type,
                    note=body.note,
                    expense_id=expense.id,
                    legacy_expense_id=None,
                    created_at=now,
                )
                session.add(payment)
                await session.flush()
                await session.commit()
                return EducationPayrollCreated(id=payment.id)
            except Exception:
                await session.rollback()
                raise

    async def delete_payroll(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        payment_id: int,
    ) -> None:
        self._require_permission(permissions, "education_payroll")
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                payment = await self._repository.teacher_payment(
                    session,
                    business_account_id=business_account_id,
                    payment_id=payment_id,
                    lock=True,
                )
                if payment is None:
                    raise ApiError(
                        404,
                        "education_payroll_not_found",
                        "Maosh to'lovi topilmadi.",
                    )
                if payment.expense_id:
                    expense = await self._repository.salary_expense(
                        session,
                        business_account_id=business_account_id,
                        expense_id=payment.expense_id,
                    )
                    if expense is not None:
                        await session.delete(expense)
                await session.delete(payment)
                await session.flush()
                await session.commit()
            except Exception:
                await session.rollback()
                raise
