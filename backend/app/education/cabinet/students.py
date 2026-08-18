"""Oquvchilar: yaratish, tahrirlash, kochirish, ochirish."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.education.cabinet.base import EducationCabinetServiceBase
from app.education.cabinet.helpers import (
    _bounded,
    _day,
    _text,
)
from app.education.model import (
    EducationStudent,
    EducationStudentGroupHistory,
)


class StudentsMixin(EducationCabinetServiceBase):
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
        transfer_date: str = "",
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
        transfer_date = transfer_date or _day(now)
        try:
            transfer_day = date.fromisoformat(transfer_date)
        except ValueError:
            raise ApiError(
                400,
                "education_transfer_date_invalid",
                "O'tkazish sanasini tanlang.",
            ) from None
        open_history = await self._repository.open_group_history(
            session,
            business_account_id=business_account_id,
            student_id=student.id,
        )
        if open_history is not None and transfer_date < open_history.started_date:
            raise ApiError(
                400,
                "education_transfer_date_invalid",
                "O'tkazish sanasi joriy guruh boshlangan sanadan oldin bo'lmaydi.",
            )
        if open_history is None and student.group_id:
            await self._start_history(
                session,
                business_account_id=business_account_id,
                student=student,
                group_id=student.group_id,
                note="Boshlang'ich guruh",
                now=now,
            )
        await self._close_history(
            session,
            business_account_id=business_account_id,
            student_id=student.id,
            now=now,
            ended_date=(transfer_day - timedelta(days=1)).isoformat(),
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
            started_date=transfer_date,
        )

    async def _student_values(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        data: dict[str, Any],
        current: EducationStudent | None,
    ) -> dict[str, Any]:
        def value(key: str, fallback: Any) -> Any:
            return data.get(key, fallback)

        full_name = _text(value("full_name", current.full_name if current else ""), 120)
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
        started_date: str = "",
    ) -> None:
        await self._repository.add_group_history(
            session,
            EducationStudentGroupHistory(
                business_account_id=business_account_id,
                legacy_source_id=None,
                student_id=student.id,
                group_id=group_id,
                started_date=started_date or student.joined_date or _day(now),
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
        ended_date: str = "",
    ) -> None:
        open_row = await self._repository.open_group_history(
            session,
            business_account_id=business_account_id,
            student_id=student_id,
        )
        if open_row is not None:
            open_row.ended_date = ended_date or _day(now)
