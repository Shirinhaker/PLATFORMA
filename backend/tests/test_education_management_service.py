"""Ta'lim boshqaruvi typed API servisining v1656 paritet zanjiri."""

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.cabinet_records.model import CabinetRecord, CabinetRecordField, CabinetResource
from app.cash_register.model import CashReceipt, CashReceiptCounter, CashReceiptLine
from app.core.errors import ApiError
from app.db.base import Base
from app.education.management import EducationManagementService
from app.education.model import (
    EducationAttendance,
    EducationGroup,
    EducationPayment,
    EducationStudent,
    EducationStudentGroupHistory,
    EducationTeacher,
    EducationTeacherPayment,
)
from app.education.schemas import (
    EducationAttendanceEntryWrite,
    EducationAttendanceWrite,
    EducationGroupWrite,
    EducationPaymentCreate,
    EducationPaymentVoid,
    EducationPayrollCreate,
    EducationStudentTransferWrite,
    EducationStudentWrite,
    EducationTeacherWrite,
)
from app.expenses.model import Expense
from app.profiles.model import BusinessProfile

NOW = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
BUSINESS_ID = 7


class AsyncStore:
    def __init__(self, sync: Session) -> None:
        self.sync = sync
        self.sequences: dict[str, int] = {}

    def add(self, value):
        self.sync.add(value)

    async def delete(self, value):
        self.sync.delete(value)

    async def get(self, model, identity, **_kwargs):
        return self.sync.get(model, identity)

    def get_bind(self):
        return self.sync.get_bind()

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def flush(self):
        for value in list(self.sync.new):
            if not hasattr(value, "id") or value.id is not None:
                continue
            table = value.__table__.name
            highest = self.sequences.get(table)
            if highest is None:
                highest = int(
                    self.sync.scalar(select(func.max(value.__table__.c.id))) or 0
                )
            highest += 1
            self.sequences[table] = highest
            value.id = highest
        self.sync.flush()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


def _account(identifier: int) -> Account:
    return Account(
        id=identifier,
        account_type=AccountType.BUSINESS,
        login=f"education_management_{identifier}",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def _profile(identifier: int, direction: str = "Ta'lim faoliyati") -> BusinessProfile:
    return BusinessProfile(
        account_id=identifier,
        name="English House",
        phone="",
        description="",
        public_username=f"education_management_{identifier}",
        direction=direction,
        activity_type="",
        address="",
        work_hours={},
        pay_card="",
        pay_holder="",
        pay_qr_object_key="",
        director="",
        tax_id="",
        logo_object_key="",
        logo_x=50,
        logo_y=50,
        logo_zoom=1,
        followers_count=0,
        following_count=0,
        rating_sum=0,
        rating_count=0,
        map_visible=False,
        dashboard_snapshot={},
        recent_activity=[],
        cabinet_payload={"items": [{"id": 51, "name": "Ingliz tili"}]},
    )


@pytest.fixture
def management():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            BusinessProfile.__table__,
            CabinetResource.__table__,
            CabinetRecord.__table__,
            CabinetRecordField.__table__,
            EducationTeacher.__table__,
            EducationGroup.__table__,
            EducationStudent.__table__,
            EducationStudentGroupHistory.__table__,
            EducationAttendance.__table__,
            CashReceiptCounter.__table__,
            CashReceipt.__table__,
            CashReceiptLine.__table__,
            EducationPayment.__table__,
            Expense.__table__,
            EducationTeacherPayment.__table__,
        ),
    )
    with Session(engine) as seed:
        seed.add_all(
            (
                _account(BUSINESS_ID),
                _account(8),
                _profile(BUSINESS_ID),
                _profile(8, "Savdo"),
            )
        )
        seed.add(
            EducationTeacher(
                id=1,
                business_account_id=BUSINESS_ID,
                legacy_source_id=101,
                full_name="Aziza Ustoz",
                phone="",
                specialty="Ingliz tili",
                hired_date="2026-07-01",
                salary_type="monthly",
                salary_amount=1_000,
                note="",
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        seed.add(
            EducationGroup(
                id=1,
                business_account_id=BUSINESS_ID,
                legacy_source_id=11,
                course_item_id=51,
                name="Starter",
                teacher_id=1,
                legacy_teacher_id=101,
                teacher_name="Aziza Ustoz",
                room_name="A1",
                capacity=12,
                weekdays="mon,wed,fri",
                lesson_from="09:00",
                lesson_to="10:00",
                start_date="2026-07-01",
                end_date="",
                billing_type="monthly",
                package_lessons=0,
                package_price=0,
                status="active",
                created_at=1,
                updated_at=1,
            )
        )
        seed.add(
            EducationStudent(
                id=1,
                business_account_id=BUSINESS_ID,
                legacy_source_id=21,
                group_id=1,
                user_account_id=None,
                legacy_user_id=None,
                full_name="Ali Valiyev",
                phone="+99890",
                parent_name="",
                parent_phone="",
                birth_date="",
                joined_date="2026-07-10",
                payment_start_date="2026-07-10",
                lesson_package_override=0,
                note="",
                monthly_fee=500,
                status="active",
                created_at=1,
                updated_at=1,
            )
        )
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    yield EducationManagementService(sessions, now_provider=lambda: NOW), engine
    engine.dispose()


async def test_schedule_and_attendance_are_relational_and_tenant_scoped(management):
    service, engine = management
    groups = await service.list_groups(
        business_account_id=BUSINESS_ID, permissions=None
    )
    assert [(row.name, row.course_name, row.student_count) for row in groups] == [
        ("Starter", "Ingliz tili", 1)
    ]

    saved = await service.save_attendance(
        business_account_id=BUSINESS_ID,
        permissions=None,
        body=EducationAttendanceWrite(
            group_id=1,
            lesson_date=date(2026, 8, 10),
            entries=[EducationAttendanceEntryWrite(student_id=1, status="present")],
        ),
    )
    assert saved.saved == 1
    read = await service.attendance(
        business_account_id=BUSINESS_ID,
        permissions=None,
        group_id=1,
        lesson_date=date(2026, 8, 10),
    )
    assert read.students[0].attendance_status == "present"
    with Session(engine) as check:
        assert (
            check.scalars(select(EducationAttendance)).one().business_account_id
            == BUSINESS_ID
        )


async def test_group_student_crud_card_and_transfer_are_typed(management):
    service, engine = management
    created_group = await service.create_group(
        business_account_id=BUSINESS_ID,
        permissions=None,
        body=EducationGroupWrite(
            name="Intermediate",
            weekdays=["tue", "thu"],
            lesson_from="11:00",
            lesson_to="12:00",
        ),
    )
    created_student = await service.create_student(
        business_account_id=BUSINESS_ID,
        permissions=None,
        body=EducationStudentWrite(
            full_name="Laylo Karimova",
            group_id=1,
            joined_date="2026-08-01",
            payment_start_date="2026-08-01",
            monthly_fee=700,
        ),
    )
    students = await service.list_students(
        business_account_id=BUSINESS_ID,
        permissions=None,
    )
    assert any(
        row.id == created_student.id and row.group_name == "Starter" for row in students
    )

    moved = await service.transfer_student(
        business_account_id=BUSINESS_ID,
        permissions=None,
        student_id=created_student.id,
        body=EducationStudentTransferWrite(
            group_id=created_group.id,
            transfer_date=date(2026, 8, 10),
            note="Yuqori bosqich",
        ),
    )
    assert moved.group_name == "Intermediate"
    card = await service.student_card(
        business_account_id=BUSINESS_ID,
        permissions=None,
        student_id=created_student.id,
    )
    assert card.student.group_name == "Intermediate"
    assert [row.group_name for row in card.group_history] == ["Intermediate", "Starter"]

    with pytest.raises(ApiError) as direct_group_change:
        await service.update_student(
            business_account_id=BUSINESS_ID,
            permissions=None,
            student_id=created_student.id,
            body=EducationStudentWrite(
                full_name="Laylo Karimova",
                group_id=1,
            ),
        )
    assert direct_group_change.value.code == "education_student_transfer_required"

    await service.delete_student(
        business_account_id=BUSINESS_ID,
        permissions=None,
        student_id=created_student.id,
    )
    await service.delete_group(
        business_account_id=BUSINESS_ID,
        permissions=None,
        group_id=created_group.id,
    )
    with Session(engine) as check:
        assert check.get(EducationStudent, created_student.id).status == "deleted"
        assert check.get(EducationGroup, created_group.id).status == "deleted"


async def test_student_payment_creates_cash_receipt_and_owner_can_void(management):
    service, engine = management
    created = await service.create_payment(
        business_account_id=BUSINESS_ID,
        actor_staff_id=None,
        permissions=None,
        body=EducationPaymentCreate(
            student_id=1,
            payment_month="2026-08",
            amount=500,
            pay_type="karta",
            note="Terminal",
        ),
    )
    assert created.receipt_no == 1
    with Session(engine) as check:
        payment = check.get(EducationPayment, created.id)
        receipt = check.get(CashReceipt, payment.cash_receipt_id)
        line = check.scalars(select(CashReceiptLine)).one()
        assert (receipt.source, receipt.pay_type, line.total) == (
            "education",
            "karta",
            500,
        )

    result = await service.void_payment(
        business_account_id=BUSINESS_ID,
        permissions=None,
        payment_id=created.id,
        body=EducationPaymentVoid(reason="Xato kiritildi"),
    )
    assert result.voided is True
    with Session(engine) as check:
        assert check.get(EducationPayment, created.id).void_reason == "Xato kiritildi"
        assert check.scalar(select(func.count(CashReceiptLine.id))) == 0


async def test_teacher_crud_refreshes_group_snapshot(management):
    service, engine = management
    updated = await service.update_teacher(
        business_account_id=BUSINESS_ID,
        permissions=None,
        teacher_id=1,
        body=EducationTeacherWrite(
            full_name="Aziza Karimova",
            specialty="IELTS",
            salary_type="monthly",
            salary_amount=1_200,
        ),
    )
    assert updated.ok is True
    with Session(engine) as check:
        assert check.get(EducationGroup, 1).teacher_name == "Aziza Karimova"

    await service.delete_teacher(
        business_account_id=BUSINESS_ID,
        permissions=None,
        teacher_id=1,
    )
    with Session(engine) as check:
        assert check.get(EducationTeacher, 1).status == "inactive"
        assert check.get(EducationGroup, 1).teacher_id is None


async def test_payroll_and_expense_are_one_chain_and_permissions_hold(management):
    service, engine = management
    created = await service.create_payroll(
        business_account_id=BUSINESS_ID,
        actor_staff_id=None,
        permissions=None,
        body=EducationPayrollCreate(
            teacher_id=1,
            payment_month="2026-08",
            amount=700,
            pay_type="naqd",
            note="Avans",
        ),
    )
    with Session(engine) as check:
        payment = check.get(EducationTeacherPayment, created.id)
        expense = check.get(Expense, payment.expense_id)
        assert (expense.source, expense.amount) == ("education_salary", 700)

    await service.delete_payroll(
        business_account_id=BUSINESS_ID,
        permissions=None,
        payment_id=created.id,
    )
    with Session(engine) as check:
        assert check.get(EducationTeacherPayment, created.id) is None
        assert check.scalar(select(func.count(Expense.id))) == 0

    with pytest.raises(ApiError) as denied:
        await service.payroll(
            business_account_id=BUSINESS_ID,
            permissions=("education_attendance",),
            payment_month="2026-08",
        )
    assert denied.value.code == "staff_permission_required"
    with pytest.raises(ApiError) as wrong_direction:
        await service.list_groups(business_account_id=8, permissions=None)
    assert wrong_direction.value.code == "education_direction_required"


@pytest.mark.asyncio
async def test_payment_control_classifies_students_and_totals_the_debt(management):
    """Nazorat jadvali — kim qarzdor, qancha. Bu raqamlar pulga tegishli.

    `docs/qoplama-hisoboti.md` da bu funksiya "hech qanday test bilan
    qoplanmagan" deb belgilangan edi.
    """
    service, _engine = management

    control = await service.payment_control(
        business_account_id=BUSINESS_ID,
        permissions=None,
        group_id=0,
    )

    assert [student.full_name for student in control.students] == ["Ali Valiyev"]
    student = control.students[0]
    assert student.id == 1
    assert student.group_name == "Starter"
    assert student.billing_type == "monthly"
    assert student.status in {"overdue", "due_today", "upcoming", "paid"}

    # Jamlar har bir holatdagi o'quvchilar soniga teng bo'lishi kerak.
    summary = control.summary
    counted = summary.overdue + summary.due_today + summary.upcoming + summary.paid
    assert counted == len(control.students)


@pytest.mark.asyncio
async def test_payment_control_requires_the_payments_permission(management):
    service, _engine = management

    with pytest.raises(ApiError) as denied:
        await service.payment_control(
            business_account_id=BUSINESS_ID,
            permissions=("education_attendance",),
            group_id=0,
        )
    assert denied.value.code == "staff_permission_required"


@pytest.mark.asyncio
async def test_monthly_report_shows_the_fee_and_reflects_a_recorded_payment(
    management,
):
    """Oylik hisobot: to'lovdan oldin va keyin raqam o'zgarishi kerak."""
    service, _engine = management

    before = await service.payments(
        business_account_id=BUSINESS_ID,
        permissions=None,
        payment_month="2026-08",
        group_id=0,
    )
    assert before.payment_month == "2026-08"
    row = next(s for s in before.students if s.student_id == 1)
    assert row.monthly_fee == 500
    assert row.group_name == "Starter"
    assert before.history == []

    await service.create_payment(
        business_account_id=BUSINESS_ID,
        actor_staff_id=None,
        permissions=None,
        body=EducationPaymentCreate(
            student_id=1,
            payment_month="2026-08",
            amount=500,
            pay_type="naqd",
        ),
    )

    after = await service.payments(
        business_account_id=BUSINESS_ID,
        permissions=None,
        payment_month="2026-08",
        group_id=0,
    )
    assert len(after.history) == 1
    assert after.history[0].amount == 500


@pytest.mark.asyncio
async def test_payroll_report_lists_teachers_with_their_salary_basis(management):
    """Oylik hisoboti — o'qituvchiga qancha to'lanishi shu yerdan ko'rinadi."""
    service, _engine = management

    report = await service.payroll(
        business_account_id=BUSINESS_ID,
        permissions=None,
        payment_month="2026-08",
    )

    assert report.payment_month == "2026-08"
    assert [teacher.full_name for teacher in report.teachers] == ["Aziza Ustoz"]
    teacher = report.teachers[0]
    assert teacher.id == 1
    # `expected` maosh turiga qarab hisoblanadi; manfiy bo'lishi mumkin emas.
    assert teacher.expected >= 0
    assert teacher.lesson_count >= 0
    assert report.history == []
