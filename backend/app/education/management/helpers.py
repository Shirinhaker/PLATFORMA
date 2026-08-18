"""O'quv markazi boshqaruvi uchun konstantalar va mayda hisoblar.

Oy/sana o'girish, to'lov holati, o'qituvchi qatori — hech biri
seansni bilmaydi, shuning uchun alohida turadi.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.education.model import (
    EducationTeacher,
)
from app.education.schemas import (
    EducationTeacherRead,
)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


NowProvider = Callable[[], datetime]


UZBEKISTAN_TZ = timezone(timedelta(hours=5))


ATTENDANCE_STATUSES = frozenset({"present", "late", "excused", "absent"})


CHARGEABLE_STATUSES = frozenset({"present", "late", "absent"})


EDUCATION_DIRECTIONS = frozenset({"Ta'lim faoliyati", "Ta’lim faoliyati"})


def _teacher_read(teacher: EducationTeacher, group_count: int) -> EducationTeacherRead:
    return EducationTeacherRead(
        id=teacher.id,
        full_name=teacher.full_name,
        phone=teacher.phone,
        specialty=teacher.specialty,
        hired_date=teacher.hired_date,
        salary_type=teacher.salary_type,
        salary_amount=teacher.salary_amount,
        note=teacher.note,
        group_count=int(group_count or 0),
    )


def _month(value: str, message: str) -> str:
    try:
        return date.fromisoformat(f"{value}-01").strftime("%Y-%m")
    except (TypeError, ValueError):
        raise ApiError(400, "education_month_invalid", message) from None


def _date(value: str, fallback: date) -> date:
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return fallback


def _student_start(student, today: date) -> date:
    return _date(student.payment_start_date or student.joined_date, today)


def _add_month(value: date, months: int = 1) -> date:
    total = value.year * 12 + value.month - 1 + months
    year, month_zero = divmod(total, 12)
    month = month_zero + 1
    next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    last_day = (next_month - timedelta(days=1)).day
    return date(year, month, min(value.day, last_day))


def _payment_local_date(value: datetime) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UZBEKISTAN_TZ).date()


def _billing_status(student, group, *, today, attendances, payments):
    start = _student_start(student, today)
    billing_type = (
        "attendance" if group and group.billing_type == "attendance" else "monthly"
    )
    expected = 0
    paid_total = 0
    next_due = ""
    lessons_done = 0
    lessons_remaining = 0
    package_lessons = 0
    payable_now = 0
    if billing_type == "attendance" and group:
        package_lessons = student.lesson_package_override or group.package_lessons
        package_price = group.package_price
        chargeable = sorted(
            (
                row
                for row in attendances
                if row.lesson_date >= start.isoformat()
                and row.attendance_status in CHARGEABLE_STATUSES
            ),
            key=lambda row: (row.lesson_date, row.id or 0),
        )
        lessons_done = len(chargeable)
        completed = lessons_done // package_lessons if package_lessons else 0
        expected = completed * package_price
        paid_total = sum(
            payment.amount
            for payment in payments
            if _payment_local_date(payment.created_at) >= start
        )
        debt = max(0, expected - paid_total)
        payable_now = (
            min(debt, package_price - (paid_total % package_price))
            if debt and package_price
            else debt
        )
        paid_packages = (
            min(completed, paid_total // package_price) if package_price else 0
        )
        if debt and package_lessons:
            offset = paid_packages * package_lessons + package_lessons - 1
            next_due = (
                chargeable[offset].lesson_date
                if offset < len(chargeable)
                else today.isoformat()
            )
        lessons_remaining = (
            package_lessons - (lessons_done % package_lessons) if package_lessons else 0
        )
    else:
        fee = student.monthly_fee
        due_dates: list[date] = []
        due = _add_month(start)
        while due <= today:
            due_dates.append(due)
            due = _add_month(due)
        expected = len(due_dates) * fee
        first_key = (
            due_dates[0].strftime("%Y-%m")
            if due_dates
            else _add_month(start).strftime("%Y-%m")
        )
        paid_total = sum(
            payment.amount for payment in payments if payment.payment_month >= first_key
        )
        debt = max(0, expected - paid_total)
        payable_now = min(debt, fee - (paid_total % fee)) if debt and fee else debt
        if debt and fee and due_dates:
            paid_cycles = min(len(due_dates) - 1, paid_total // fee)
            next_due = due_dates[paid_cycles].isoformat()
        else:
            next_due = due.isoformat()
    debt = max(0, expected - paid_total)
    delta = (date.fromisoformat(next_due) - today).days if next_due else 9_999
    if debt and delta < 0:
        status = "overdue"
    elif debt and delta == 0:
        status = "due_today"
    elif (
        billing_type == "attendance"
        and not debt
        and package_lessons
        and lessons_remaining <= 2
    ) or (not debt and 0 <= delta <= 3):
        status = "upcoming"
    elif debt:
        status = "due_today"
    else:
        status = "paid"
    return {
        "billing_type": billing_type,
        "status": status,
        "start_date": start,
        "next_due": next_due,
        "expected": expected,
        "paid": paid_total,
        "debt": debt,
        "package_lessons": package_lessons,
        "lessons_done": lessons_done,
        "lessons_remaining": lessons_remaining,
        "payable_now": payable_now,
        "payment_month": (next_due or today.isoformat())[:7],
    }
