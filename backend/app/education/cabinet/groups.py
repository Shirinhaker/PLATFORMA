"""Guruhlar: yaratish, tahrirlash, ochirish."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.education.cabinet.base import EducationCabinetServiceBase
from app.education.cabinet.helpers import (
    BILLING_TYPES,
    _bounded,
    _text,
    _weekdays,
)
from app.education.model import (
    EducationGroup,
)


class GroupsMixin(EducationCabinetServiceBase):
    async def create_group_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        profile,
        data: dict[str, Any],
        now: int,
    ) -> int:
        values = await self._group_values(
            session,
            business_account_id=business_account_id,
            profile=profile,
            data=data,
            current=None,
        )
        group = EducationGroup(
            business_account_id=business_account_id,
            legacy_source_id=None,
            status="active",
            created_at=now,
            updated_at=now,
            **values,
        )
        await self._repository.add_group(session, group)
        return group.id

    async def update_group_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        profile,
        group_id: int,
        data: dict[str, Any],
        now: int,
    ) -> None:
        group = await self._repository.owned_group(
            session,
            business_account_id=business_account_id,
            group_id=group_id,
            lock=True,
        )
        if group is None:
            raise ApiError(404, "education_group_not_found", "Guruh topilmadi.")
        values = await self._group_values(
            session,
            business_account_id=business_account_id,
            profile=profile,
            data=data,
            current=group,
        )
        for name, value in values.items():
            setattr(group, name, value)
        group.updated_at = now

    async def delete_group_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        group_id: int,
        now: int,
    ) -> None:
        """v1656 kabi yumshoq o'chirish — yozuv arxivda qoladi."""
        group = await self._repository.owned_group(
            session,
            business_account_id=business_account_id,
            group_id=group_id,
            lock=True,
        )
        if group is None:
            raise ApiError(404, "education_group_not_found", "Guruh topilmadi.")
        group.status = "deleted"
        group.updated_at = now

    async def _group_values(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        profile,
        data: dict[str, Any],
        current: EducationGroup | None,
    ) -> dict[str, Any]:
        def value(key: str, fallback: Any) -> Any:
            return data[key] if key in data else fallback

        name = _text(value("name", current.name if current else ""), 80)
        if not name:
            raise ApiError(
                400, "education_group_name_required", "Guruh nomini kiriting."
            )

        raw_course = value(
            "course_item_id",
            current.course_item_id if current else None,
        )
        course_item_id: int | None
        if raw_course in (None, "", 0, "0"):
            course_item_id = None
        else:
            try:
                course_item_id = int(raw_course)
            except (TypeError, ValueError):
                raise ApiError(
                    400,
                    "education_course_invalid",
                    "Kurs noto'g'ri tanlangan.",
                ) from None
            items = await self._repository.catalog_rows(session, profile)
            known = {
                str(row.get("id"))
                for row in items
                if str(row.get("kind") or "") == "service"
            }
            if str(course_item_id) not in known:
                raise ApiError(
                    400,
                    "education_course_not_found",
                    "Tanlangan kurs topilmadi.",
                )

        billing_type = _text(
            value(
                "billing_type",
                current.billing_type if current else "monthly",
            ),
            20,
        )
        if billing_type not in BILLING_TYPES:
            billing_type = "monthly"
        package_lessons = _bounded(
            value("package_lessons", current.package_lessons if current else 0),
            low=0,
            high=1000,
            message="Darslar soni yoki paket narxi noto'g'ri.",
        )
        package_price = _bounded(
            value("package_price", current.package_price if current else 0),
            low=0,
            high=10**12,
            message="Darslar soni yoki paket narxi noto'g'ri.",
        )
        if billing_type == "attendance" and (
            package_lessons <= 0 or package_price <= 0
        ):
            raise ApiError(
                400,
                "education_package_required",
                "Qatnashuv bo'yicha hisoblash uchun darslar soni va "
                "paket narxini kiriting.",
            )

        raw_teacher = value("teacher_id", current.teacher_id if current else None)
        teacher_id = None
        teacher_name = _text(
            value("teacher_name", current.teacher_name if current else ""),
            160,
        )
        if raw_teacher not in (None, "", 0, "0"):
            try:
                teacher_id = int(raw_teacher)
            except (TypeError, ValueError):
                raise ApiError(
                    400,
                    "education_teacher_invalid",
                    "O'qituvchi noto'g'ri tanlangan.",
                ) from None
            teacher = await self._repository.owned_teacher(
                session,
                business_account_id=business_account_id,
                teacher_id=teacher_id,
            )
            if teacher is None:
                raise ApiError(
                    400,
                    "education_teacher_not_found",
                    "Tanlangan o'qituvchi topilmadi.",
                )
            teacher_name = teacher.full_name

        return {
            "name": name,
            "course_item_id": course_item_id,
            "teacher_id": teacher_id,
            "teacher_name": teacher_name,
            "room_name": _text(
                value("room_name", current.room_name if current else ""), 80
            ),
            "capacity": _bounded(
                value("capacity", current.capacity if current else 0),
                low=0,
                high=10000,
                message="O'quvchilar sig'imi noto'g'ri.",
            ),
            "weekdays": _weekdays(
                value("weekdays", current.weekdays if current else "")
            ),
            "lesson_from": _text(
                value("lesson_from", current.lesson_from if current else ""), 5
            ),
            "lesson_to": _text(
                value("lesson_to", current.lesson_to if current else ""), 5
            ),
            "start_date": _text(
                value("start_date", current.start_date if current else ""), 20
            ),
            "end_date": _text(
                value("end_date", current.end_date if current else ""), 20
            ),
            "billing_type": billing_type,
            "package_lessons": package_lessons,
            "package_price": package_price,
        }
