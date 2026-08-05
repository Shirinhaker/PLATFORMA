from __future__ import annotations

import calendar
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.education.schemas import (
    EducationStatisticsFinanceRead,
    EducationStatisticsGroupRead,
    EducationStatisticsPeriodRead,
    EducationStatisticsProcessRead,
    EducationStatisticsReportRead,
    EducationStatisticsResultRead,
)
from app.education.statistics_repository import EducationStatisticsRepository


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NowProvider = Callable[[], datetime]
UZBEKISTAN_TZ = timezone(timedelta(hours=5))
PERIODS = ("day", "month", "year")


@dataclass(frozen=True)
class EducationPeriodWindow:
    period: str
    selected: date
    start_date: date
    end_date: date
    start: datetime
    end: datetime
    months: tuple[str, ...]


def _add_months(value: date, months: int) -> date:
    offset = value.month - 1 + months
    return date(value.year + offset // 12, offset % 12 + 1, 1)


def _local_start(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UZBEKISTAN_TZ)


class EducationStatisticsService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: EducationStatisticsRepository | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or EducationStatisticsRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def report(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        period: str,
        selected_date: str,
    ) -> EducationStatisticsReportRead:
        self._require_permission(permissions)
        window = self._window(period, selected_date)
        start_date = window.start_date.isoformat()
        end_date = window.end_date.isoformat()

        async with self._session_factory() as session:
            direction = await self._repository.business_direction(
                session,
                business_account_id=business_account_id,
            )
            if direction not in {"Ta'lim faoliyati", "Ta’lim faoliyati"}:
                raise ApiError(
                    403,
                    "education_direction_required",
                    "Bu bo‘lim faqat Ta’lim faoliyati yo‘nalishi uchun.",
                )

            process = await self._repository.process_summary(
                session,
                business_account_id=business_account_id,
                start_date=start_date,
                end_date=end_date,
                start_epoch=int(window.start.timestamp()),
                end_epoch=int(window.end.timestamp()),
            )
            raw_groups = await self._repository.group_rows(
                session,
                business_account_id=business_account_id,
                start_date=start_date,
                end_date=end_date,
            )
            students = await self._repository.active_students(
                session,
                business_account_id=business_account_id,
            )
            attendance_billing = await self._repository.attendance_billing_rows(
                session,
                business_account_id=business_account_id,
                start_date=start_date,
                end_date=end_date,
            )
            student_payments = await self._repository.student_payment_rows(
                session,
                business_account_id=business_account_id,
                start=window.start,
                end=window.end,
            )
            teachers = await self._repository.active_teachers(
                session,
                business_account_id=business_account_id,
            )
            teacher_lessons = await self._repository.teacher_lesson_rows(
                session,
                business_account_id=business_account_id,
                start_date=start_date,
                end_date=end_date,
            )
            teacher_paid = await self._repository.teacher_paid(
                session,
                business_account_id=business_account_id,
                start=window.start,
                end=window.end,
            )
            other_expenses = await self._repository.other_expenses(
                session,
                business_account_id=business_account_id,
                start=window.start,
                end=window.end,
            )

        groups = {
            int(row.id): EducationStatisticsGroupRead(
                id=int(row.id),
                name=str(row.name or "Guruh"),
                active_students=int(row.active_students or 0),
                attendance_percent=self._percent(
                    int(row.attendance_present or 0),
                    int(row.attendance_total or 0),
                ),
            )
            for row in raw_groups
        }
        lesson_counts = {
            (int(row.student_id), str(row.month)): int(row.lessons or 0)
            for row in attendance_billing
            if row.student_id is not None
        }

        student_due = 0
        for student in students:
            expected = self._student_due(student, window, lesson_counts)
            student_due += expected
            if student.group_id is not None and int(student.group_id) in groups:
                groups[int(student.group_id)].calculated += expected

        student_paid = 0
        for payment in student_payments:
            amount = int(payment.amount or 0)
            student_paid += amount
            if payment.group_id is not None and int(payment.group_id) in groups:
                groups[int(payment.group_id)].paid += amount
        for group in groups.values():
            group.debt = max(0, group.calculated - group.paid)

        teacher_lesson_counts = {
            int(row.teacher_id): int(row.lessons or 0)
            for row in teacher_lessons
            if row.teacher_id is not None
        }
        teacher_due = sum(
            self._teacher_due(teacher, window, teacher_lesson_counts)
            for teacher in teachers
        )

        attendance_total = int(process.attendance_total or 0)
        attendance_present = int(process.attendance_present or 0)
        return EducationStatisticsReportRead(
            period=EducationStatisticsPeriodRead(
                type=window.period,
                date=window.selected.isoformat(),
                start=start_date,
                end=end_date,
            ),
            education=EducationStatisticsProcessRead(
                active_students=int(process.active_students or 0),
                active_groups=int(process.active_groups or 0),
                new_enrollments=int(process.new_enrollments or 0),
                attendance_percent=self._percent(
                    attendance_present,
                    attendance_total,
                ),
            ),
            student_finance=EducationStatisticsFinanceRead(
                calculated=student_due,
                paid=student_paid,
                debt=max(0, student_due - student_paid),
            ),
            teacher_finance=EducationStatisticsFinanceRead(
                calculated=teacher_due,
                paid=teacher_paid,
                debt=max(0, teacher_due - teacher_paid),
            ),
            result=EducationStatisticsResultRead(
                other_expenses=other_expenses,
                cash_flow=student_paid - teacher_paid - other_expenses,
                accrual_result=student_due - teacher_due - other_expenses,
            ),
            groups=list(groups.values()),
        )

    def shift(self, period: str, selected_date: str, direction: int) -> str:
        window = self._window(period, selected_date)
        step = -1 if direction < 0 else 1
        if window.period == "day":
            return (window.selected + timedelta(days=step)).isoformat()
        if window.period == "month":
            return _add_months(window.selected.replace(day=1), step).isoformat()
        return date(window.selected.year + step, 1, 1).isoformat()

    def _window(self, period: str, selected_date: str) -> EducationPeriodWindow:
        normalized = str(period or "month").strip().lower()
        if normalized not in PERIODS:
            raise ApiError(
                400,
                "education_statistics_period_invalid",
                "Davr turi noto‘g‘ri.",
            )
        if str(selected_date or "").strip():
            try:
                selected = date.fromisoformat(str(selected_date).strip())
            except ValueError:
                raise ApiError(
                    400,
                    "education_statistics_date_invalid",
                    "Statistika sanasi noto‘g‘ri.",
                ) from None
        else:
            selected = self._now_provider().astimezone(UZBEKISTAN_TZ).date()

        if normalized == "day":
            start_date = end_date = selected
        elif normalized == "month":
            start_date = selected.replace(day=1)
            end_date = selected.replace(
                day=calendar.monthrange(selected.year, selected.month)[1]
            )
        else:
            start_date = selected.replace(month=1, day=1)
            end_date = selected.replace(month=12, day=31)

        months: list[str] = []
        current = start_date.replace(day=1)
        last = end_date.replace(day=1)
        while current <= last:
            months.append(current.strftime("%Y-%m"))
            current = _add_months(current, 1)

        start = _local_start(start_date).astimezone(UTC)
        end = _local_start(end_date + timedelta(days=1)).astimezone(UTC)
        return EducationPeriodWindow(
            period=normalized,
            selected=selected,
            start_date=start_date,
            end_date=end_date,
            start=start,
            end=end,
            months=tuple(months),
        )

    @staticmethod
    def _student_due(student, window, lesson_counts: dict[tuple[int, str], int]) -> int:
        billing_type = str(student.billing_type or "monthly")
        package_lessons = int(student.package_lessons or 0)
        package_price = int(student.package_price or 0)
        if billing_type == "attendance" and package_lessons > 0:
            total = 0
            for month in window.months:
                lessons = min(
                    lesson_counts.get((int(student.id), month), 0),
                    package_lessons,
                )
                total += int(round(package_price / package_lessons * lessons))
            return total
        if window.period == "day":
            return 0
        joined = str(student.joined_date or "")[:7]
        eligible = sum(not joined or joined <= month for month in window.months)
        return int(student.monthly_fee or 0) * eligible

    @staticmethod
    def _teacher_due(teacher, window, lesson_counts: dict[int, int]) -> int:
        salary = int(teacher.salary_amount or 0)
        if str(teacher.salary_type or "monthly") == "per_lesson":
            return lesson_counts.get(int(teacher.id), 0) * salary
        if window.period == "day":
            return 0
        hired = str(teacher.hired_date or "")[:7]
        eligible = sum(not hired or hired <= month for month in window.months)
        return salary * eligible

    @staticmethod
    def _percent(present: int, total: int) -> int:
        return int(round(present * 100 / total)) if total else 0

    @staticmethod
    def _require_permission(permissions: tuple[str, ...] | None) -> None:
        if permissions is not None and "education_statistics" not in permissions:
            raise ApiError(
                403,
                "staff_permission_required",
                "Bu bo‘limga vakolatingiz yo‘q.",
            )
