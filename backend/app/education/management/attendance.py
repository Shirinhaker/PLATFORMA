"""Davomat: kunlik belgilash va o'qish."""

from __future__ import annotations

from datetime import date

from app.core.errors import ApiError
from app.education.management.base import EducationManagementServiceBase
from app.education.management.helpers import (
    ATTENDANCE_STATUSES,
)
from app.education.model import (
    EducationAttendance,
)
from app.education.schemas import (
    EducationAttendanceRead,
    EducationAttendanceSaved,
    EducationAttendanceStudentRead,
    EducationAttendanceWrite,
)


class AttendanceMixin(EducationManagementServiceBase):
    async def attendance(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        group_id: int,
        lesson_date: date,
    ) -> EducationAttendanceRead:
        self._require_permission(permissions, "education_attendance")
        async with self._session_factory() as session:
            profile = await self._require_scope(session, business_account_id)
            groups = await self._groups_in_session(
                session,
                business_account_id=business_account_id,
                profile=profile,
            )
            group = next((row for row in groups if row.id == group_id), None)
            if group is None:
                raise ApiError(404, "education_group_not_found", "Guruh topilmadi.")
            rows = await self._repository.attendance_for_day(
                session,
                business_account_id=business_account_id,
                group_id=group_id,
                lesson_date=lesson_date.isoformat(),
            )
            students = [
                EducationAttendanceStudentRead(
                    student_id=student.id,
                    full_name=student.full_name,
                    phone=student.phone,
                    attendance_status=(
                        attendance.attendance_status if attendance else ""
                    ),
                    attendance_note=(attendance.note if attendance else ""),
                )
                for student, attendance in rows
            ]
            await session.rollback()
            return EducationAttendanceRead(
                group=group,
                lesson_date=lesson_date,
                students=students,
            )

    async def save_attendance(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        body: EducationAttendanceWrite,
    ) -> EducationAttendanceSaved:
        self._require_permission(permissions, "education_attendance")
        now = self._now_provider()
        lesson_date = body.lesson_date.isoformat()
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                group = await self._repository.active_group(
                    session,
                    business_account_id=business_account_id,
                    group_id=body.group_id,
                    lock=True,
                )
                if group is None:
                    raise ApiError(404, "education_group_not_found", "Guruh topilmadi.")
                roster = await self._repository.active_students_with_groups(
                    session,
                    business_account_id=business_account_id,
                    group_id=body.group_id,
                )
                valid_students = {student.id for student, _group in roster}
                existing = {
                    row.student_id: row
                    for row in await self._repository.existing_attendance(
                        session,
                        business_account_id=business_account_id,
                        group_id=body.group_id,
                        lesson_date=lesson_date,
                    )
                    if row.student_id is not None
                }
                saved = 0
                for entry in body.entries:
                    if (
                        entry.student_id not in valid_students
                        or entry.status not in ATTENDANCE_STATUSES
                    ):
                        continue
                    attendance = existing.get(entry.student_id)
                    if attendance is None:
                        attendance = EducationAttendance(
                            business_account_id=business_account_id,
                            legacy_source_id=None,
                            group_id=body.group_id,
                            student_id=entry.student_id,
                            legacy_group_id=None,
                            legacy_student_id=None,
                            lesson_date=lesson_date,
                            attendance_status=entry.status,
                            note=entry.note,
                            created_at=now,
                            updated_at=now,
                        )
                        session.add(attendance)
                        existing[entry.student_id] = attendance
                    else:
                        attendance.attendance_status = entry.status
                        attendance.note = entry.note
                        attendance.updated_at = now
                    saved += 1
                await session.flush()
                await session.commit()
                return EducationAttendanceSaved(saved=saved)
            except Exception:
                await session.rollback()
                raise
