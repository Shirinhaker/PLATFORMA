"""Oquv kabineti uchun konstantalar."""

from __future__ import annotations

from datetime import timedelta

from app.core.errors import ApiError

"""Ta'lim kabineti: guruh va o'quvchi boshqaruvi.

Yozuvlar `education_groups`, `education_students` jadvallariga tushadi.
Barcha metodlar chaqiruvchining tranzaksiyasida ishlaydi — kabinet
amali bir nechta yozuvni birga o'zgartirganda hammasi birga qaytadi.

Tekshiruvlar v1656 (`api.py:_education_group_payload`,
`_education_student_payload`) bilan bir xil.
"""


WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


BILLING_TYPES = ("monthly", "attendance")


def _text(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _bounded(value: object, *, low: int, high: int, message: str) -> int:
    try:
        number = int(str(value or 0).replace(" ", ""))
    except (TypeError, ValueError):
        raise ApiError(400, "education_number_invalid", message) from None
    return max(low, min(high, number))


def _weekdays(value: object) -> str:
    days = value if isinstance(value, list) else str(value or "").split(",")
    return ",".join(
        day for day in (str(item).strip() for item in days) if day in WEEKDAYS
    )


def _day(now: int) -> str:
    from datetime import UTC, datetime

    return (datetime.fromtimestamp(now, UTC) + timedelta(hours=5)).strftime("%Y-%m-%d")
