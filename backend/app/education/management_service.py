"""v1656 ta'lim boshqaruvini typed relatsion APIga ko'chirish.

Dars jadvali guruhlardan hosil qilinadi. Davomat, o'quvchi to'lovi,
o'qituvchi va maosh amallari o'z jadvallarida tenant bo'yicha ajratiladi.
To'lov Kassa bilan, maosh esa Xarajatlar bilan bitta tranzaksiyada yoziladi.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.cash_register.model import CashReceipt, CashReceiptLine
from app.cash_register.repository import CashRegisterRepository
from app.core.errors import ApiError
from app.education.cabinet_service import EducationCabinetService
from app.education.management_repository import EducationManagementRepository
from app.education.model import (
    EducationAttendance,
    EducationPayment,
    EducationStudent,
    EducationTeacher,
    EducationTeacherPayment,
)
from app.education.repository import EducationEnrollmentRepository
from app.education.schemas import (
    EducationAttendanceRead,
    EducationAttendanceSaved,
    EducationAttendanceStudentRead,
    EducationAttendanceWrite,
    EducationCreated,
    EducationGroupRead,
    EducationGroupWrite,
    EducationPaymentControlRead,
    EducationPaymentControlStudentRead,
    EducationPaymentControlSummaryRead,
    EducationPaymentCreate,
    EducationPaymentCreated,
    EducationPaymentHistoryRead,
    EducationPaymentMonthRead,
    EducationPaymentStudentRead,
    EducationPaymentVoid,
    EducationPaymentVoided,
    EducationPayrollCreate,
    EducationPayrollCreated,
    EducationPayrollHistoryRead,
    EducationPayrollRead,
    EducationPayrollTeacherRead,
    EducationTeacherCreated,
    EducationTeacherRead,
    EducationTeacherUpdated,
    EducationTeacherWrite,
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
from app.expenses.model import Expense


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NowProvider = Callable[[], datetime]
UZBEKISTAN_TZ = timezone(timedelta(hours=5))
ATTENDANCE_STATUSES = frozenset({"present", "late", "excused", "absent"})
CHARGEABLE_STATUSES = frozenset({"present", "late", "absent"})
EDUCATION_DIRECTIONS = frozenset({"Ta'lim faoliyati", "Ta’lim faoliyati"})


class EducationManagementService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: EducationManagementRepository | None = None,
        enrollment_repository: EducationEnrollmentRepository | None = None,
        cash_repository: CashRegisterRepository | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or EducationManagementRepository()
        self._education = enrollment_repository or EducationEnrollmentRepository()
        self._cabinet = EducationCabinetService(repository=self._education)
        self._cash = cash_repository or CashRegisterRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def list_groups(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
    ) -> list[EducationGroupRead]:
        self._require_any_education(permissions)
        async with self._session_factory() as session:
            profile = await self._require_scope(session, business_account_id)
            result = await self._groups_in_session(
                session,
                business_account_id=business_account_id,
                profile=profile,
            )
            await session.rollback()
            return result

    async def create_group(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        body: EducationGroupWrite,
    ) -> EducationCreated:
        self._require_permission(permissions, "education_groups")
        now = self._now_provider()
        async with self._session_factory() as session:
            try:
                profile = await self._require_scope(session, business_account_id)
                group_id = await self._cabinet.create_group_in_session(
                    session,
                    business_account_id=business_account_id,
                    profile=profile,
                    data=body.model_dump(),
                    now=int(now.timestamp()),
                )
                await session.commit()
                return EducationCreated(id=group_id)
            except Exception:
                await session.rollback()
                raise

    async def update_group(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        group_id: int,
        body: EducationGroupWrite,
    ) -> EducationUpdated:
        self._require_permission(permissions, "education_groups")
        now = self._now_provider()
        async with self._session_factory() as session:
            try:
                profile = await self._require_scope(session, business_account_id)
                await self._cabinet.update_group_in_session(
                    session,
                    business_account_id=business_account_id,
                    profile=profile,
                    group_id=group_id,
                    data=body.model_dump(),
                    now=int(now.timestamp()),
                )
                await session.commit()
                return EducationUpdated()
            except Exception:
                await session.rollback()
                raise

    async def delete_group(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        group_id: int,
    ) -> None:
        self._require_permission(permissions, "education_groups")
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                await self._cabinet.delete_group_in_session(
                    session,
                    business_account_id=business_account_id,
                    group_id=group_id,
                    now=int(self._now_provider().timestamp()),
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise

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
                raise ApiError(404, "education_student_not_found", "O'quvchi topilmadi.")
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
            counts = {name: 0 for name in ATTENDANCE_STATUSES}
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
            month_attendance = [row for row in attendances if row.lesson_date.startswith(month)]
            month_payments = [row for row in active_payments if row.payment_month == month]
            expected = student.monthly_fee
            if group and group.billing_type == "attendance" and group.package_lessons > 0:
                lessons = sum(
                    row.attendance_status in CHARGEABLE_STATUSES
                    for row in month_attendance
                )
                expected = round(
                    group.package_price / group.package_lessons
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
                    attendance_status=(attendance.attendance_status if attendance else ""),
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
                    raise ApiError(
                        404, "education_group_not_found", "Guruh topilmadi."
                    )
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

    async def payment_control(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        group_id: int,
    ) -> EducationPaymentControlRead:
        self._require_permission(permissions, "education_payments")
        today = self._now_provider().astimezone(UZBEKISTAN_TZ).date()
        async with self._session_factory() as session:
            await self._require_scope(session, business_account_id)
            rows = await self._repository.active_students_with_groups(
                session,
                business_account_id=business_account_id,
                group_id=group_id,
            )
            students = [student for student, _group in rows]
            starts = [_student_start(student, today) for student in students]
            minimum_start = min(starts, default=today).isoformat()
            minimum_month = min(
                (_add_month(start).strftime("%Y-%m") for start in starts),
                default=today.strftime("%Y-%m"),
            )
            attendance_rows = await self._repository.attendance_rows(
                session,
                business_account_id=business_account_id,
                student_ids=[student.id for student in students],
                start_date=minimum_start,
            )
            payment_rows = await self._repository.active_payments(
                session,
                business_account_id=business_account_id,
                student_ids=[student.id for student in students],
                minimum_month=minimum_month,
            )
            attendance_by_student: dict[int, list[EducationAttendance]] = {}
            for row in attendance_rows:
                if row.student_id is not None:
                    attendance_by_student.setdefault(row.student_id, []).append(row)
            payments_by_student: dict[int, list[EducationPayment]] = {}
            for row in payment_rows:
                if row.student_id is not None:
                    payments_by_student.setdefault(row.student_id, []).append(row)

            summary = EducationPaymentControlSummaryRead()
            output: list[EducationPaymentControlStudentRead] = []
            for student, group in rows:
                values = _billing_status(
                    student,
                    group,
                    today=today,
                    attendances=attendance_by_student.get(student.id, []),
                    payments=payments_by_student.get(student.id, []),
                )
                output.append(EducationPaymentControlStudentRead(
                    id=student.id,
                    group_id=student.group_id,
                    full_name=student.full_name,
                    phone=student.phone,
                    parent_phone=student.parent_phone,
                    group_name=group.name if group else "",
                    **values,
                ))
                setattr(summary, values["status"], getattr(summary, values["status"]) + 1)
                summary.total_debt += values["debt"]
            await session.rollback()
            return EducationPaymentControlRead(
                today=today,
                summary=summary,
                students=output,
            )

    async def payments(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        payment_month: str,
        group_id: int,
    ) -> EducationPaymentMonthRead:
        self._require_permission(permissions, "education_payments")
        month = _month(payment_month, "To'lov oyini tanlang.")
        async with self._session_factory() as session:
            await self._require_scope(session, business_account_id)
            rows = await self._repository.active_students_with_groups(
                session,
                business_account_id=business_account_id,
                group_id=group_id,
            )
            student_ids = [student.id for student, _group in rows]
            attendance = await self._repository.attendance_rows(
                session,
                business_account_id=business_account_id,
                student_ids=student_ids,
                start_date=f"{month}-01",
                month=month,
            )
            chargeable: dict[int, int] = {}
            for row in attendance:
                if (
                    row.student_id is not None
                    and row.attendance_status in CHARGEABLE_STATUSES
                ):
                    chargeable[row.student_id] = chargeable.get(row.student_id, 0) + 1
            totals = await self._repository.payment_totals(
                session,
                business_account_id=business_account_id,
                student_ids=student_ids,
                minimum_month=month,
            )
            paid = {
                int(student_id): int(amount or 0)
                for student_id, payment_key, amount in totals
                if student_id is not None and payment_key == month
            }
            students: list[EducationPaymentStudentRead] = []
            for student, group in rows:
                billing_type = (
                    group.billing_type if group and group.billing_type == "attendance"
                    else "monthly"
                )
                lessons = chargeable.get(student.id, 0)
                package_lessons = group.package_lessons if group else 0
                package_price = group.package_price if group else 0
                if billing_type == "attendance" and package_lessons > 0:
                    counted = min(lessons, package_lessons)
                    expected = round(package_price / package_lessons * counted)
                    per_lesson = round(package_price / package_lessons)
                else:
                    expected = student.monthly_fee
                    per_lesson = 0
                paid_amount = paid.get(student.id, 0)
                students.append(EducationPaymentStudentRead(
                    student_id=student.id,
                    full_name=student.full_name,
                    phone=student.phone,
                    monthly_fee=student.monthly_fee,
                    group_name=group.name if group else "",
                    billing_type=billing_type,
                    package_lessons=package_lessons,
                    package_price=package_price,
                    chargeable_lessons=lessons,
                    per_lesson_price=per_lesson,
                    expected=expected,
                    paid=paid_amount,
                    debt=max(0, expected - paid_amount),
                ))
            history_rows = await self._repository.payment_history(
                session,
                business_account_id=business_account_id,
                payment_month=month,
            )
            history = [
                EducationPaymentHistoryRead(
                    id=payment.id,
                    student_id=payment.student_id,
                    full_name=str(full_name or "O'quvchi"),
                    payment_month=payment.payment_month,
                    amount=payment.amount,
                    pay_type=("karta" if payment.pay_type == "karta" else "naqd"),
                    note=payment.note,
                    voided_at=payment.voided_at,
                    void_reason=payment.void_reason,
                    created_at=payment.created_at,
                )
                for payment, full_name in history_rows
            ]
            await session.rollback()
            return EducationPaymentMonthRead(
                payment_month=month,
                students=students,
                history=history,
            )

    async def create_payment(
        self,
        *,
        business_account_id: int,
        actor_staff_id: int | None,
        permissions: tuple[str, ...] | None,
        body: EducationPaymentCreate,
    ) -> EducationPaymentCreated:
        self._require_permission(permissions, "education_payments")
        month = _month(body.payment_month, "To'lov oyini tanlang.")
        now = self._now_provider()
        today = now.astimezone(UZBEKISTAN_TZ).date()
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                student = await self._repository.active_student(
                    session,
                    business_account_id=business_account_id,
                    student_id=body.student_id,
                    lock=True,
                )
                if student is None:
                    raise ApiError(
                        404, "education_student_not_found", "O'quvchi topilmadi."
                    )
                group = None
                if student.group_id:
                    group = await self._repository.active_group(
                        session,
                        business_account_id=business_account_id,
                        group_id=student.group_id,
                    )
                if group and group.billing_type == "attendance":
                    start = _student_start(student, today)
                    attendance = await self._repository.attendance_rows(
                        session,
                        business_account_id=business_account_id,
                        student_ids=[student.id],
                        start_date=start.isoformat(),
                    )
                    payments = await self._repository.active_payments(
                        session,
                        business_account_id=business_account_id,
                        student_ids=[student.id],
                        minimum_month=start.strftime("%Y-%m"),
                    )
                    remaining = _billing_status(
                        student,
                        group,
                        today=today,
                        attendances=attendance,
                        payments=payments,
                    )["debt"]
                    if remaining <= 0:
                        raise ApiError(
                            400,
                            "education_package_not_due",
                            "Hozircha to'lanadigan tugallangan dars paketi yo'q.",
                        )
                else:
                    if student.monthly_fee <= 0:
                        raise ApiError(
                            400,
                            "education_monthly_fee_required",
                            "O'quvchining oylik to'lov summasi belgilanmagan.",
                        )
                    totals = await self._repository.payment_totals(
                        session,
                        business_account_id=business_account_id,
                        student_ids=[student.id],
                        minimum_month=month,
                    )
                    already_paid = sum(
                        int(amount or 0)
                        for _student_id, key, amount in totals
                        if key == month
                    )
                    remaining = max(0, student.monthly_fee - already_paid)
                if body.amount > remaining:
                    raise ApiError(
                        400,
                        "education_payment_exceeds_debt",
                        "Kiritilgan summa qolgan qarzdorlikdan ko'p.",
                    )

                receipt_no = await self._cash.next_receipt_no(
                    session,
                    business_account_id=business_account_id,
                    now=now,
                )
                receipt = CashReceipt(
                    business_account_id=business_account_id,
                    receipt_no=receipt_no,
                    source="education",
                    order_id=None,
                    legacy_order_source_id=None,
                    legacy_group_key=None,
                    pay_type=body.pay_type,
                    debtor_id=None,
                    debtor_name_snapshot="",
                    legacy_debtor_source_id=None,
                    note=("Ta'lim to'lovi" + (f": {body.note}" if body.note else ""))[:200],
                    created_by_staff_id=actor_staff_id,
                    actor_name_snapshot="",
                    waiter_staff_id=None,
                    waiter_name_snapshot="",
                    created_at=now,
                )
                session.add(receipt)
                await session.flush()
                line = CashReceiptLine(
                    receipt_id=receipt.id,
                    business_account_id=business_account_id,
                    catalog_item_id=None,
                    inventory_item_id=None,
                    legacy_source_key=None,
                    item_name=f"{student.full_name} — {month}"[:220],
                    qty=Decimal("1"),
                    unit="oy",
                    unit_price=body.amount,
                    total=body.amount,
                    cost_total=0,
                    created_at=now,
                )
                session.add(line)
                payment = EducationPayment(
                    business_account_id=business_account_id,
                    legacy_source_id=None,
                    student_id=student.id,
                    legacy_student_id=student.legacy_source_id,
                    payment_month=month,
                    amount=body.amount,
                    pay_type=body.pay_type,
                    note=body.note,
                    legacy_sale_id=None,
                    cash_receipt_id=receipt.id,
                    voided_at=None,
                    legacy_voided_by=None,
                    void_reason="",
                    created_at=now,
                )
                session.add(payment)
                await session.flush()
                await session.commit()
                return EducationPaymentCreated(
                    id=payment.id,
                    receipt_no=receipt_no,
                )
            except Exception:
                await session.rollback()
                raise

    async def void_payment(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        payment_id: int,
        body: EducationPaymentVoid,
    ) -> EducationPaymentVoided:
        self._require_owner(permissions, "O'quvchi to'lovini bekor qilish")
        now = self._now_provider()
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                payment = await self._repository.payment(
                    session,
                    business_account_id=business_account_id,
                    payment_id=payment_id,
                    lock=True,
                )
                if payment is None:
                    raise ApiError(
                        404, "education_payment_not_found", "To'lov topilmadi."
                    )
                if payment.voided_at is not None:
                    raise ApiError(
                        400,
                        "education_payment_already_voided",
                        "Bu to'lov avval bekor qilingan.",
                    )
                payment.voided_at = now
                payment.void_reason = body.reason
                if payment.cash_receipt_id:
                    receipt = await self._repository.cash_receipt(
                        session,
                        business_account_id=business_account_id,
                        receipt_id=payment.cash_receipt_id,
                        lock=True,
                    )
                    if receipt is not None:
                        await self._repository.clear_cash_receipt_lines(
                            session,
                            business_account_id=business_account_id,
                            receipt_id=receipt.id,
                        )
                        receipt.note = (
                            "Ta'lim to'lovi bekor qilindi: " + body.reason
                        )[:200]
                await session.flush()
                await session.commit()
                return EducationPaymentVoided()
            except Exception:
                await session.rollback()
                raise

    async def list_teachers(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
    ) -> list[EducationTeacherRead]:
        self._require_permission(permissions, "education_teachers")
        async with self._session_factory() as session:
            await self._require_scope(session, business_account_id)
            rows = await self._repository.active_teachers(
                session,
                business_account_id=business_account_id,
            )
            result = [_teacher_read(teacher, group_count) for teacher, group_count in rows]
            await session.rollback()
            return result

    async def create_teacher(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        body: EducationTeacherWrite,
    ) -> EducationTeacherCreated:
        self._require_permission(permissions, "education_teachers")
        now = self._now_provider()
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                teacher = EducationTeacher(
                    business_account_id=business_account_id,
                    legacy_source_id=None,
                    status="active",
                    created_at=now,
                    updated_at=now,
                    **body.model_dump(),
                )
                session.add(teacher)
                await session.flush()
                await session.commit()
                return EducationTeacherCreated(id=teacher.id)
            except Exception:
                await session.rollback()
                raise

    async def update_teacher(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        teacher_id: int,
        body: EducationTeacherWrite,
    ) -> EducationTeacherUpdated:
        self._require_permission(permissions, "education_teachers")
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                teacher = await self._repository.active_teacher(
                    session,
                    business_account_id=business_account_id,
                    teacher_id=teacher_id,
                    lock=True,
                )
                if teacher is None:
                    raise ApiError(
                        404, "education_teacher_not_found", "O'qituvchi topilmadi."
                    )
                for name, value in body.model_dump().items():
                    setattr(teacher, name, value)
                teacher.updated_at = self._now_provider()
                await self._repository.update_teacher_snapshot(
                    session,
                    business_account_id=business_account_id,
                    teacher_id=teacher.id,
                    full_name=teacher.full_name,
                )
                await session.commit()
                return EducationTeacherUpdated()
            except Exception:
                await session.rollback()
                raise

    async def delete_teacher(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        teacher_id: int,
    ) -> None:
        self._require_permission(permissions, "education_teachers")
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                teacher = await self._repository.active_teacher(
                    session,
                    business_account_id=business_account_id,
                    teacher_id=teacher_id,
                    lock=True,
                )
                if teacher is None:
                    raise ApiError(
                        404, "education_teacher_not_found", "O'qituvchi topilmadi."
                    )
                teacher.status = "inactive"
                teacher.updated_at = self._now_provider()
                await self._repository.unlink_teacher(
                    session,
                    business_account_id=business_account_id,
                    teacher_id=teacher.id,
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise

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
                    lesson_counts[int(teacher_id)] = lesson_counts.get(int(teacher_id), 0) + 1
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
                output.append(EducationPayrollTeacherRead(
                    id=teacher.id,
                    full_name=teacher.full_name,
                    salary_type=teacher.salary_type,
                    salary_amount=teacher.salary_amount,
                    lesson_count=lessons,
                    expected=expected,
                    paid=paid_amount,
                    debt=max(0, expected - paid_amount),
                ))
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
                lessons = sum(1 for teacher_id, _group, _day in lesson_rows if teacher_id == teacher.id)
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

    async def _groups_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        profile,
    ) -> list[EducationGroupRead]:
        rows = await self._repository.active_groups(
            session,
            business_account_id=business_account_id,
        )
        catalog = await self._education.catalog_rows(session, profile)
        course_names = {
            str(row.get("id")): str(row.get("name") or "")
            for row in catalog
            if isinstance(row, dict)
        }
        return [
            EducationGroupRead(
                id=group.id,
                course_item_id=group.course_item_id,
                course_name=course_names.get(str(group.course_item_id or ""), ""),
                name=group.name,
                teacher_id=group.teacher_id,
                teacher_name=group.teacher_name,
                room_name=group.room_name,
                capacity=group.capacity,
                weekdays=group.weekdays,
                lesson_from=group.lesson_from,
                lesson_to=group.lesson_to,
                start_date=group.start_date,
                end_date=group.end_date,
                billing_type=(
                    "attendance" if group.billing_type == "attendance" else "monthly"
                ),
                package_lessons=group.package_lessons,
                package_price=group.package_price,
                student_count=int(student_count or 0),
            )
            for group, student_count in rows
        ]

    async def _require_scope(
        self,
        session: AsyncSession,
        business_account_id: int,
    ):
        profile = await self._repository.profile(session, business_account_id)
        if profile is None:
            raise ApiError(404, "business_profile_not_found", "Biznes profil topilmadi.")
        if profile.direction not in EDUCATION_DIRECTIONS:
            raise ApiError(
                403,
                "education_direction_required",
                "Bu bo'lim faqat Ta'lim faoliyati yo'nalishi uchun.",
            )
        return profile

    @staticmethod
    def _require_permission(
        permissions: tuple[str, ...] | None,
        required: str,
    ) -> None:
        if permissions is not None and required not in permissions:
            raise ApiError(
                403,
                "staff_permission_required",
                "Bu bo'limga vakolatingiz yo'q.",
            )

    @staticmethod
    def _require_any_education(permissions: tuple[str, ...] | None) -> None:
        if permissions is None:
            return
        if not any(value.startswith("education_") for value in permissions):
            raise ApiError(
                403,
                "staff_permission_required",
                "Bu bo'limga vakolatingiz yo'q.",
            )

    @staticmethod
    def _require_owner(
        permissions: tuple[str, ...] | None,
        action: str,
    ) -> None:
        if permissions is not None:
            raise ApiError(
                403,
                "business_owner_required",
                f"{action} faqat biznes egasi uchun.",
            )


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
                row for row in attendances
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
            if debt and package_price else debt
        )
        paid_packages = min(completed, paid_total // package_price) if package_price else 0
        if debt and package_lessons:
            offset = paid_packages * package_lessons + package_lessons - 1
            next_due = (
                chargeable[offset].lesson_date
                if offset < len(chargeable) else today.isoformat()
            )
        lessons_remaining = (
            package_lessons - (lessons_done % package_lessons)
            if package_lessons else 0
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
            if due_dates else _add_month(start).strftime("%Y-%m")
        )
        paid_total = sum(
            payment.amount
            for payment in payments
            if payment.payment_month >= first_key
        )
        debt = max(0, expected - paid_total)
        payable_now = (
            min(debt, fee - (paid_total % fee)) if debt and fee else debt
        )
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
