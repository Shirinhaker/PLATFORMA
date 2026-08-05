"""Ta'lim kabineti: guruh va o'quvchi boshqaruvi.

Yozuvlar `education_groups`, `education_students` jadvallariga tushadi.
Barcha metodlar chaqiruvchining tranzaksiyasida ishlaydi — kabinet
amali bir nechta yozuvni birga o'zgartirganda hammasi birga qaytadi.

Tekshiruvlar v1656 (`api.py:_education_group_payload`,
`_education_student_payload`) bilan bir xil.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.education.model import (
    EducationGroup,
    EducationStudent,
    EducationStudentGroupHistory,
)
from app.education.repository import EducationEnrollmentRepository


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


class EducationCabinetService:
    def __init__(
        self,
        *,
        repository: EducationEnrollmentRepository | None = None,
    ) -> None:
        self._repository = repository or EducationEnrollmentRepository()

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

    async def create_student_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        data: dict[str, Any],
        now: int,
    ) -> int:
        values = await self._student_values(
            session,
            business_account_id=business_account_id,
            data=data,
            current=None,
        )
        student = EducationStudent(
            business_account_id=business_account_id,
            legacy_source_id=None,
            user_account_id=None,
            legacy_user_id=None,
            status="active",
            created_at=now,
            updated_at=now,
            **values,
        )
        await self._repository.add_student(session, student)
        if student.group_id:
            await self._start_history(
                session,
                business_account_id=business_account_id,
                student=student,
                group_id=student.group_id,
                note="Boshlang'ich guruh",
                now=now,
            )
        return student.id

    async def update_student_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        student_id: int,
        data: dict[str, Any],
        now: int,
    ) -> None:
        student = await self._repository.owned_student(
            session,
            business_account_id=business_account_id,
            student_id=student_id,
            lock=True,
        )
        if student is None:
            raise ApiError(
                404,
                "education_student_not_found",
                "O'quvchi topilmadi.",
            )
        previous_group = student.group_id
        values = await self._student_values(
            session,
            business_account_id=business_account_id,
            data=data,
            current=student,
        )
        for name, value in values.items():
            setattr(student, name, value)
        student.updated_at = now
        if student.group_id != previous_group and student.group_id:
            await self._close_history(
                session,
                business_account_id=business_account_id,
                student_id=student.id,
                now=now,
            )
            await self._start_history(
                session,
                business_account_id=business_account_id,
                student=student,
                group_id=student.group_id,
                note="Guruh o'zgartirildi",
                now=now,
            )

    async def delete_student_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        student_id: int,
        now: int,
    ) -> None:
        student = await self._repository.owned_student(
            session,
            business_account_id=business_account_id,
            student_id=student_id,
            lock=True,
        )
        if student is None:
            raise ApiError(
                404,
                "education_student_not_found",
                "O'quvchi topilmadi.",
            )
        student.status = "deleted"
        student.updated_at = now
        await self._close_history(
            session,
            business_account_id=business_account_id,
            student_id=student.id,
            now=now,
        )

    async def transfer_student_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        student_id: int,
        group_id: int,
        note: str,
        now: int,
    ) -> None:
        """O'quvchini boshqa guruhga ko'chiradi va tarixni yopadi."""
        student = await self._repository.owned_student(
            session,
            business_account_id=business_account_id,
            student_id=student_id,
            lock=True,
        )
        if student is None:
            raise ApiError(
                404,
                "education_student_not_found",
                "O'quvchi topilmadi.",
            )
        group = await self._repository.owned_group(
            session,
            business_account_id=business_account_id,
            group_id=group_id,
        )
        if group is None:
            raise ApiError(
                400,
                "education_group_required",
                "Tanlangan guruh topilmadi.",
            )
        if student.group_id == group.id:
            raise ApiError(
                400,
                "education_student_same_group",
                "O'quvchi allaqachon shu guruhda.",
            )
        await self._close_history(
            session,
            business_account_id=business_account_id,
            student_id=student.id,
            now=now,
        )
        student.group_id = group.id
        student.updated_at = now
        await self._start_history(
            session,
            business_account_id=business_account_id,
            student=student,
            group_id=group.id,
            note=_text(note, 500) or "Guruhga ko'chirildi",
            now=now,
        )

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
            raise ApiError(400, "education_group_name_required", "Guruh nomini kiriting.")

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
        if raw_teacher not in (None, "", 0, "0"):
            try:
                teacher_id = int(raw_teacher)
            except (TypeError, ValueError):
                raise ApiError(
                    400,
                    "education_teacher_invalid",
                    "O'qituvchi noto'g'ri tanlangan.",
                ) from None

        return {
            "name": name,
            "course_item_id": course_item_id,
            "teacher_id": teacher_id,
            "teacher_name": _text(
                value("teacher_name", current.teacher_name if current else ""),
                160,
            ),
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

    async def _student_values(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        data: dict[str, Any],
        current: EducationStudent | None,
    ) -> dict[str, Any]:
        def value(key: str, fallback: Any) -> Any:
            return data[key] if key in data else fallback

        full_name = _text(
            value("full_name", current.full_name if current else ""), 120
        )
        if not full_name:
            raise ApiError(
                400,
                "education_student_name_required",
                "O'quvchi ism-familiyasini kiriting.",
            )

        raw_group = value("group_id", current.group_id if current else None)
        group_id: int | None
        if raw_group in (None, "", 0, "0"):
            group_id = None
        else:
            try:
                group_id = int(raw_group)
            except (TypeError, ValueError):
                raise ApiError(
                    400,
                    "education_group_invalid",
                    "Guruh noto'g'ri tanlangan.",
                ) from None
            group = await self._repository.owned_group(
                session,
                business_account_id=business_account_id,
                group_id=group_id,
            )
            if group is None:
                raise ApiError(
                    400,
                    "education_group_required",
                    "Tanlangan guruh topilmadi.",
                )

        return {
            "full_name": full_name,
            "group_id": group_id,
            "phone": _text(value("phone", current.phone if current else ""), 40),
            "parent_name": _text(
                value("parent_name", current.parent_name if current else ""), 160
            ),
            "parent_phone": _text(
                value("parent_phone", current.parent_phone if current else ""), 40
            ),
            "birth_date": _text(
                value("birth_date", current.birth_date if current else ""), 20
            ),
            "joined_date": _text(
                value("joined_date", current.joined_date if current else ""), 20
            ),
            "payment_start_date": _text(
                value(
                    "payment_start_date",
                    current.payment_start_date if current else "",
                ),
                20,
            ),
            "note": _text(value("note", current.note if current else ""), 2000),
            "monthly_fee": _bounded(
                value("monthly_fee", current.monthly_fee if current else 0),
                low=0,
                high=10**12,
                message="To'lov summasi yoki darslar soni noto'g'ri.",
            ),
            "lesson_package_override": _bounded(
                value(
                    "lesson_package_override",
                    current.lesson_package_override if current else 0,
                ),
                low=0,
                high=1000,
                message="To'lov summasi yoki darslar soni noto'g'ri.",
            ),
        }

    async def _start_history(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        student: EducationStudent,
        group_id: int,
        note: str,
        now: int,
    ) -> None:
        await self._repository.add_group_history(
            session,
            EducationStudentGroupHistory(
                business_account_id=business_account_id,
                legacy_source_id=None,
                student_id=student.id,
                group_id=group_id,
                started_date=student.joined_date or _day(now),
                ended_date="",
                note=note,
                created_at=now,
            ),
        )

    async def _close_history(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        student_id: int,
        now: int,
    ) -> None:
        open_row = await self._repository.open_group_history(
            session,
            business_account_id=business_account_id,
            student_id=student_id,
        )
        if open_row is not None:
            open_row.ended_date = _day(now)


def _day(now: int) -> str:
    from datetime import UTC, datetime, timedelta

    return (
        datetime.fromtimestamp(now, UTC) + timedelta(hours=5)
    ).strftime("%Y-%m-%d")
