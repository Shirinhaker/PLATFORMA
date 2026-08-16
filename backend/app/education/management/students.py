"""O'quvchilar: ro'yxat, kartochka, guruhdan guruhga ko'chirish."""

from __future__ import annotations

from app.core.errors import ApiError
from app.education.management.base import EducationManagementServiceBase
from app.education.management.helpers import (
    ATTENDANCE_STATUSES,
    CHARGEABLE_STATUSES,
    UZBEKISTAN_TZ,
)
from app.education.model import (
    EducationStudent,
)
from app.education.schemas import (
    EducationCreated,
    EducationGroupRead,
    EducationStudentAttendanceCounts,
    EducationStudentAttendanceSummary,
    EducationStudentCardRead,
    EducationStudentGroupHistoryRead,
    EducationStudentPaymentRead,
    EducationStudentPaymentSummary,
    EducationStudentRead,
    EducationStudentTransferred,
    EducationStudentTransferWrite,
    EducationStudentWrite,
    EducationUpdated,
)


class StudentsMixin(EducationManagementServiceBase):
    async def list_students(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        group_id: int = 0,
    ) -> list[EducationStudentRead]:
        self._require_permission(permissions, "education_students")
        async with self._session_factory() as session:
            profile = await self._require_scope(session, business_account_id)
            groups = {
                group.id: group
                for group in await self._groups_in_session(
                    session,
                    business_account_id=business_account_id,
                    profile=profile,
                )
            }
            rows = await self._repository.active_students_with_groups(
                session,
                business_account_id=business_account_id,
                group_id=group_id,
            )
            result = [
                self._student_read(student, groups.get(student.group_id or 0))
                for student, _group in rows
            ]
            await session.rollback()
            return result

    async def create_student(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        body: EducationStudentWrite,
    ) -> EducationCreated:
        self._require_permission(permissions, "education_students")
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                student_id = await self._cabinet.create_student_in_session(
                    session,
                    business_account_id=business_account_id,
                    data=body.model_dump(),
                    now=int(self._now_provider().timestamp()),
                )
                await session.commit()
                return EducationCreated(id=student_id)
            except Exception:
                await session.rollback()
                raise

    async def update_student(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        student_id: int,
        body: EducationStudentWrite,
    ) -> EducationUpdated:
        self._require_permission(permissions, "education_students")
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                student = await self._repository.active_student(
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
                if body.group_id != student.group_id:
                    raise ApiError(
                        400,
                        "education_student_transfer_required",
                        "Guruhni o'quvchi kartasidagi o'tkazish tugmasi orqali almashtiring.",
                    )
                await self._cabinet.update_student_in_session(
                    session,
                    business_account_id=business_account_id,
                    student_id=student_id,
                    data=body.model_dump(),
                    now=int(self._now_provider().timestamp()),
                )
                await session.commit()
                return EducationUpdated()
            except Exception:
                await session.rollback()
                raise

    async def delete_student(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        student_id: int,
    ) -> None:
        self._require_permission(permissions, "education_students")
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                await self._cabinet.delete_student_in_session(
                    session,
                    business_account_id=business_account_id,
                    student_id=student_id,
                    now=int(self._now_provider().timestamp()),
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def student_card(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        student_id: int,
    ) -> EducationStudentCardRead:
        self._require_permission(permissions, "education_students")
        today = self._now_provider().astimezone(UZBEKISTAN_TZ).date()
        month = today.strftime("%Y-%m")
        async with self._session_factory() as session:
            profile = await self._require_scope(session, business_account_id)
            student = await self._repository.active_student(
                session,
                business_account_id=business_account_id,
                student_id=student_id,
            )
            if student is None:
                raise ApiError(
                    404, "education_student_not_found", "O'quvchi topilmadi."
                )
            groups = {
                group.id: group
                for group in await self._groups_in_session(
                    session,
                    business_account_id=business_account_id,
                    profile=profile,
                )
            }
            group = groups.get(student.group_id or 0)
            attendances = await self._repository.attendance_rows(
                session,
                business_account_id=business_account_id,
                student_ids=[student.id],
                start_date="0001-01-01",
            )
            counts = dict.fromkeys(ATTENDANCE_STATUSES, 0)
            for row in attendances:
                if row.attendance_status in counts:
                    counts[row.attendance_status] += 1
            total = sum(counts.values())
            attended = counts["present"] + counts["late"]
            all_payments = await self._repository.student_payments(
                session,
                business_account_id=business_account_id,
                student_id=student.id,
            )
            active_payments = [row for row in all_payments if row.voided_at is None]
            month_attendance = [
                row for row in attendances if row.lesson_date.startswith(month)
            ]
            month_payments = [
                row for row in active_payments if row.payment_month == month
            ]
            expected = student.monthly_fee
            if (
                group
                and group.billing_type == "attendance"
                and group.package_lessons > 0
            ):
                lessons = sum(
                    row.attendance_status in CHARGEABLE_STATUSES
                    for row in month_attendance
                )
                expected = round(
                    group.package_price
                    / group.package_lessons
                    * min(lessons, group.package_lessons)
                )
            paid = sum(row.amount for row in month_payments)
            history_rows = await self._repository.student_group_history(
                session,
                business_account_id=business_account_id,
                student_id=student.id,
            )
            result = EducationStudentCardRead(
                student=self._student_read(student, group),
                attendance=EducationStudentAttendanceSummary(
                    total=total,
                    attended=attended,
                    percent=round(attended * 100 / total) if total else 0,
                    counts=EducationStudentAttendanceCounts(**counts),
                ),
                payment=EducationStudentPaymentSummary(
                    expected=expected,
                    paid=paid,
                    debt=max(0, expected - paid),
                    total_paid=sum(row.amount for row in active_payments),
                ),
                payments=[
                    EducationStudentPaymentRead(
                        id=row.id,
                        payment_month=row.payment_month,
                        amount=row.amount,
                        pay_type="karta" if row.pay_type == "karta" else "naqd",
                        note=row.note,
                        voided_at=row.voided_at,
                        void_reason=row.void_reason,
                        created_at=row.created_at,
                    )
                    for row in all_payments
                ],
                group_history=[
                    EducationStudentGroupHistoryRead(
                        id=row.id,
                        group_id=row.group_id,
                        group_name=str(group_name or ""),
                        started_date=row.started_date,
                        ended_date=row.ended_date,
                        note=row.note,
                    )
                    for row, group_name in history_rows
                ],
            )
            await session.rollback()
            return result

    async def transfer_student(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        student_id: int,
        body: EducationStudentTransferWrite,
    ) -> EducationStudentTransferred:
        self._require_permission(permissions, "education_students")
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                await self._cabinet.transfer_student_in_session(
                    session,
                    business_account_id=business_account_id,
                    student_id=student_id,
                    group_id=body.group_id,
                    transfer_date=body.transfer_date.isoformat(),
                    note=body.note,
                    now=int(self._now_provider().timestamp()),
                )
                group = await self._repository.active_group(
                    session,
                    business_account_id=business_account_id,
                    group_id=body.group_id,
                )
                await session.commit()
                return EducationStudentTransferred(
                    group_id=body.group_id,
                    group_name=group.name if group else "",
                )
            except Exception:
                await session.rollback()
                raise

    @staticmethod
    def _student_read(
        student: EducationStudent,
        group: EducationGroupRead | None,
    ) -> EducationStudentRead:
        return EducationStudentRead(
            id=student.id,
            full_name=student.full_name,
            group_id=student.group_id,
            group_name=group.name if group else "",
            course_name=group.course_name if group else "",
            phone=student.phone,
            parent_name=student.parent_name,
            parent_phone=student.parent_phone,
            birth_date=student.birth_date,
            joined_date=student.joined_date,
            monthly_fee=student.monthly_fee,
            payment_start_date=student.payment_start_date,
            lesson_package_override=student.lesson_package_override,
            note=student.note,
        )
