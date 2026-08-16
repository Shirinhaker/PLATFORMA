"""To'lovlar: nazorat jadvali, qabul qilish, bekor qilish.

Eng katta bo'lim — to'lov qabul qilinganda qarz, chek va davomat
bir vaqtda hisobga olinadi.
"""

from __future__ import annotations

from decimal import Decimal

from app.cash_register.model import CashReceipt, CashReceiptLine
from app.core.errors import ApiError
from app.education.management.base import EducationManagementServiceBase
from app.education.management.helpers import (
    CHARGEABLE_STATUSES,
    UZBEKISTAN_TZ,
    _add_month,
    _billing_status,
    _month,
    _student_start,
)
from app.education.model import (
    EducationAttendance,
    EducationPayment,
)
from app.education.schemas import (
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
)


class PaymentsMixin(EducationManagementServiceBase):
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
                output.append(
                    EducationPaymentControlStudentRead(
                        id=student.id,
                        group_id=student.group_id,
                        full_name=student.full_name,
                        phone=student.phone,
                        parent_phone=student.parent_phone,
                        group_name=group.name if group else "",
                        **values,
                    )
                )
                setattr(
                    summary, values["status"], getattr(summary, values["status"]) + 1
                )
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
                    group.billing_type
                    if group and group.billing_type == "attendance"
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
                students.append(
                    EducationPaymentStudentRead(
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
                    )
                )
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
                    note=("Ta'lim to'lovi" + (f": {body.note}" if body.note else ""))[
                        :200
                    ],
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
                        receipt.note = ("Ta'lim to'lovi bekor qilindi: " + body.reason)[
                            :200
                        ]
                await session.flush()
                await session.commit()
                return EducationPaymentVoided()
            except Exception:
                await session.rollback()
                raise
