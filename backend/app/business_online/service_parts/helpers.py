"""Kabinet resurslari uchun konstantalar va mayda yordamchilar."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.education.repository import (
    ENROLLMENTS as EDUCATION_ENROLLMENTS,
)
from app.education.repository import (
    GROUPS as EDUCATION_GROUPS,
)
from app.education.repository import (
    STUDENTS as EDUCATION_STUDENTS,
)

SessionFactory = Callable[[], AsyncIterator[AsyncSession]]


CatalogSync = Callable[..., Awaitable[None]]


ListingSync = Callable[..., Awaitable[None]]


InventorySync = Callable[..., Awaitable[None]]


RELATIONAL_EDUCATION_RESOURCES = (
    EDUCATION_GROUPS,
    EDUCATION_STUDENTS,
    EDUCATION_ENROLLMENTS,
)


RELATIONAL_EDUCATION_WRITES = (EDUCATION_GROUPS, EDUCATION_STUDENTS)


def _record_id(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError(
            404,
            "business_online_record_not_found",
            "Yozuv topilmadi.",
        ) from None
