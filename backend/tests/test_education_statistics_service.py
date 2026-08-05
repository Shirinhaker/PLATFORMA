from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.catalog.model import CatalogItem
from app.core.errors import ApiError
from app.db.base import Base
from app.education.model import (
    CourseEnrollment,
    EducationAttendance,
    EducationGroup,
    EducationPayment,
    EducationStudent,
    EducationTeacher,
    EducationTeacherPayment,
)
from app.education.statistics_service import EducationStatisticsService
from app.expenses.model import Expense
from app.inventory.model import InventoryItem, StockMove
from app.profiles.model import BusinessProfile
from app.staff.model import StaffMember


NOW = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)  # O'zbekistonda 14:00


class AsyncStore:
    def __init__(self, sync: Session) -> None:
        self.sync = sync

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)


def account(identifier: int) -> Account:
    return Account(
        id=identifier,
        account_type=AccountType.BUSINESS,
        login=f"education_stats_{identifier}",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def profile(identifier: int, direction: str = "Ta'lim faoliyati") -> BusinessProfile:
    return BusinessProfile(
        account_id=identifier,
        name=f"O'quv markaz {identifier}",
        phone="",
        description="",
        public_username=f"education_stats_{identifier}",
        direction=direction,
        activity_type="",
        address="",
        latitude=None,
        longitude=None,
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
        cabinet_payload={},
    )


@pytest.fixture
def education_statistics_context():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            BusinessProfile.__table__,
            EducationTeacher.__table__,
            EducationGroup.__table__,
            EducationStudent.__table__,
            CourseEnrollment.__table__,
            EducationAttendance.__table__,
            EducationPayment.__table__,
            EducationTeacherPayment.__table__,
            StaffMember.__table__,
            CatalogItem.__table__,
            InventoryItem.__table__,
            StockMove.__table__,
            Expense.__table__,
        ),
    )
    with Session(engine) as seed:
        seed.add_all((
            account(1),
            account(2),
            account(3),
            profile(1),
            profile(2),
            profile(3, "Savdo"),
            EducationTeacher(
                id=11,
                business_account_id=1,
                legacy_source_id=101,
                full_name="Oylik ustoz",
                phone="",
                specialty="",
                hired_date="2026-07-01",
                salary_type="monthly",
                salary_amount=500,
                note="",
                status="active",
                created_at=NOW,
                updated_at=NOW,
            ),
            EducationTeacher(
                id=12,
                business_account_id=1,
                legacy_source_id=102,
                full_name="Darsbay ustoz",
                phone="",
                specialty="",
                hired_date="2026-08-01",
                salary_type="per_lesson",
                salary_amount=100,
                note="",
                status="active",
                created_at=NOW,
                updated_at=NOW,
            ),
            EducationTeacher(
                id=21,
                business_account_id=2,
                legacy_source_id=201,
                full_name="Begona ustoz",
                phone="",
                specialty="",
                hired_date="2026-01-01",
                salary_type="monthly",
                salary_amount=900_000,
                note="",
                status="active",
                created_at=NOW,
                updated_at=NOW,
            ),
            EducationGroup(
                id=1,
                business_account_id=1,
                legacy_source_id=101,
                course_item_id=None,
                teacher_id=11,
                legacy_teacher_id=101,
                teacher_name="Oylik ustoz",
                name="Oylik guruh",
                room_name="",
                capacity=20,
                weekdays="mon,wed,fri",
                lesson_from="09:00",
                lesson_to="10:00",
                start_date="2026-07-01",
                end_date="",
                billing_type="monthly",
                package_lessons=0,
                package_price=0,
                status="active",
                created_at=1_753_000_000,
                updated_at=1_753_000_000,
            ),
            EducationGroup(
                id=2,
                business_account_id=1,
                legacy_source_id=102,
                course_item_id=None,
                teacher_id=12,
                legacy_teacher_id=102,
                teacher_name="Darsbay ustoz",
                name="Darsbay guruh",
                room_name="",
                capacity=20,
                weekdays="tue,thu,sat",
                lesson_from="11:00",
                lesson_to="12:00",
                start_date="2026-08-01",
                end_date="",
                billing_type="attendance",
                package_lessons=8,
                package_price=800,
                status="active",
                created_at=1_753_000_000,
                updated_at=1_753_000_000,
            ),
            EducationGroup(
                id=3,
                business_account_id=2,
                legacy_source_id=201,
                course_item_id=None,
                teacher_id=21,
                legacy_teacher_id=201,
                teacher_name="Begona ustoz",
                name="Begona guruh",
                room_name="",
                capacity=20,
                weekdays="mon",
                lesson_from="09:00",
                lesson_to="10:00",
                start_date="2026-01-01",
                end_date="",
                billing_type="monthly",
                package_lessons=0,
                package_price=0,
                status="active",
                created_at=1_753_000_000,
                updated_at=1_753_000_000,
            ),
            EducationStudent(
                id=1,
                business_account_id=1,
                legacy_source_id=101,
                group_id=1,
                user_account_id=None,
                legacy_user_id=None,
                full_name="Oylik o'quvchi",
                phone="",
                parent_name="",
                parent_phone="",
                birth_date="",
                joined_date="2026-07-15",
                payment_start_date="",
                lesson_package_override=0,
                note="",
                monthly_fee=1_000,
                status="active",
                created_at=1_753_000_000,
                updated_at=1_753_000_000,
            ),
            EducationStudent(
                id=2,
                business_account_id=1,
                legacy_source_id=102,
                group_id=2,
                user_account_id=None,
                legacy_user_id=None,
                full_name="Darsbay o'quvchi",
                phone="",
                parent_name="",
                parent_phone="",
                birth_date="",
                joined_date="2026-08-01",
                payment_start_date="",
                lesson_package_override=0,
                note="",
                monthly_fee=9_999,
                status="active",
                created_at=1_753_000_000,
                updated_at=1_753_000_000,
            ),
            EducationStudent(
                id=3,
                business_account_id=2,
                legacy_source_id=201,
                group_id=3,
                user_account_id=None,
                legacy_user_id=None,
                full_name="Begona o'quvchi",
                phone="",
                parent_name="",
                parent_phone="",
                birth_date="",
                joined_date="2026-01-01",
                payment_start_date="",
                lesson_package_override=0,
                note="",
                monthly_fee=900_000,
                status="active",
                created_at=1_753_000_000,
                updated_at=1_753_000_000,
            ),
            CourseEnrollment(
                id=1,
                business_account_id=1,
                legacy_source_id=301,
                legacy_business_id=None,
                course_item_id=1,
                user_account_id=None,
                legacy_user_id=1,
                customer_name="Yangi o'quvchi",
                phone="",
                note="",
                status="new",
                group_id=None,
                created_at=int(NOW.timestamp()),
                updated_at=int(NOW.timestamp()),
            ),
            CourseEnrollment(
                id=2,
                business_account_id=2,
                legacy_source_id=302,
                legacy_business_id=None,
                course_item_id=1,
                user_account_id=None,
                legacy_user_id=2,
                customer_name="Begona ariza",
                phone="",
                note="",
                status="new",
                group_id=None,
                created_at=int(NOW.timestamp()),
                updated_at=int(NOW.timestamp()),
            ),
            EducationAttendance(
                id=1,
                business_account_id=1,
                legacy_source_id=401,
                group_id=1,
                student_id=1,
                legacy_group_id=101,
                legacy_student_id=101,
                lesson_date="2026-08-04",
                attendance_status="present",
                note="",
                created_at=NOW,
                updated_at=NOW,
            ),
            EducationAttendance(
                id=2,
                business_account_id=1,
                legacy_source_id=402,
                group_id=2,
                student_id=2,
                legacy_group_id=102,
                legacy_student_id=102,
                lesson_date="2026-08-04",
                attendance_status="present",
                note="",
                created_at=NOW,
                updated_at=NOW,
            ),
            EducationAttendance(
                id=3,
                business_account_id=1,
                legacy_source_id=403,
                group_id=2,
                student_id=2,
                legacy_group_id=102,
                legacy_student_id=102,
                lesson_date="2026-08-05",
                attendance_status="absent",
                note="",
                created_at=NOW,
                updated_at=NOW,
            ),
            EducationAttendance(
                id=4,
                business_account_id=1,
                legacy_source_id=404,
                group_id=2,
                student_id=2,
                legacy_group_id=102,
                legacy_student_id=102,
                lesson_date="2026-08-06",
                attendance_status="excused",
                note="",
                created_at=NOW,
                updated_at=NOW,
            ),
            EducationAttendance(
                id=5,
                business_account_id=2,
                legacy_source_id=405,
                group_id=3,
                student_id=3,
                legacy_group_id=201,
                legacy_student_id=201,
                lesson_date="2026-08-04",
                attendance_status="present",
                note="",
                created_at=NOW,
                updated_at=NOW,
            ),
            EducationPayment(
                id=1,
                business_account_id=1,
                legacy_source_id=501,
                student_id=1,
                legacy_student_id=101,
                payment_month="2026-08",
                amount=600,
                pay_type="naqd",
                note="",
                legacy_sale_id=None,
                voided_at=None,
                legacy_voided_by=None,
                void_reason="",
                created_at=NOW,
            ),
            EducationPayment(
                id=2,
                business_account_id=1,
                legacy_source_id=502,
                student_id=2,
                legacy_student_id=102,
                payment_month="2026-08",
                amount=150,
                pay_type="karta",
                note="",
                legacy_sale_id=None,
                voided_at=None,
                legacy_voided_by=None,
                void_reason="",
                created_at=NOW,
            ),
            EducationPayment(
                id=3,
                business_account_id=1,
                legacy_source_id=503,
                student_id=2,
                legacy_student_id=102,
                payment_month="2026-08",
                amount=99_999,
                pay_type="naqd",
                note="",
                legacy_sale_id=None,
                voided_at=NOW,
                legacy_voided_by=1,
                void_reason="xato",
                created_at=NOW,
            ),
            EducationPayment(
                id=4,
                business_account_id=2,
                legacy_source_id=504,
                student_id=3,
                legacy_student_id=201,
                payment_month="2026-08",
                amount=900_000,
                pay_type="naqd",
                note="",
                legacy_sale_id=None,
                voided_at=None,
                legacy_voided_by=None,
                void_reason="",
                created_at=NOW,
            ),
            EducationTeacherPayment(
                id=1,
                business_account_id=1,
                legacy_source_id=601,
                teacher_id=11,
                legacy_teacher_id=101,
                payment_month="2026-08",
                amount=200,
                pay_type="naqd",
                note="",
                expense_id=None,
                legacy_expense_id=None,
                created_at=NOW,
            ),
            EducationTeacherPayment(
                id=2,
                business_account_id=2,
                legacy_source_id=602,
                teacher_id=21,
                legacy_teacher_id=201,
                payment_month="2026-08",
                amount=800_000,
                pay_type="naqd",
                note="",
                expense_id=None,
                legacy_expense_id=None,
                created_at=NOW,
            ),
            Expense(
                id=1,
                business_account_id=1,
                legacy_source_id=None,
                category="Ijara",
                amount=100,
                note="",
                source="manual",
                inventory_stock_move_id=None,
                performed_by_staff_id=None,
                actor_name_snapshot="",
                created_at=NOW,
            ),
            Expense(
                id=2,
                business_account_id=1,
                legacy_source_id=None,
                category="Maosh",
                amount=200,
                note="",
                source="education_salary",
                inventory_stock_move_id=None,
                performed_by_staff_id=None,
                actor_name_snapshot="",
                created_at=NOW,
            ),
            Expense(
                id=3,
                business_account_id=2,
                legacy_source_id=None,
                category="Begona",
                amount=999_999,
                note="",
                source="manual",
                inventory_stock_move_id=None,
                performed_by_staff_id=None,
                actor_name_snapshot="",
                created_at=NOW,
            ),
        ))
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    try:
        yield EducationStatisticsService(sessions, now_provider=lambda: NOW), engine
    finally:
        engine.dispose()


async def test_month_report_matches_v1656_education_formulas(
    education_statistics_context,
):
    service, _engine = education_statistics_context

    report = await service.report(
        business_account_id=1,
        permissions=None,
        period="month",
        selected_date="2026-08-04",
    )

    assert report.period.model_dump() == {
        "type": "month",
        "date": "2026-08-04",
        "start": "2026-08-01",
        "end": "2026-08-31",
    }
    assert report.education.model_dump() == {
        "active_students": 2,
        "active_groups": 2,
        "new_enrollments": 1,
        "attendance_percent": 50,
    }
    assert report.student_finance.model_dump() == {
        "calculated": 1_200,
        "paid": 750,
        "debt": 450,
    }
    assert report.teacher_finance.model_dump() == {
        "calculated": 800,
        "paid": 200,
        "debt": 600,
    }
    assert report.result.model_dump() == {
        "other_expenses": 100,
        "cash_flow": 450,
        "accrual_result": 300,
    }
    assert [row.model_dump() for row in report.groups] == [
        {
            "id": 2,
            "name": "Darsbay guruh",
            "active_students": 1,
            "attendance_percent": 33,
            "calculated": 200,
            "paid": 150,
            "debt": 50,
        },
        {
            "id": 1,
            "name": "Oylik guruh",
            "active_students": 1,
            "attendance_percent": 100,
            "calculated": 1_000,
            "paid": 600,
            "debt": 400,
        },
    ]


async def test_day_period_does_not_accrue_monthly_fees_or_monthly_salary(
    education_statistics_context,
):
    service, _engine = education_statistics_context

    report = await service.report(
        business_account_id=1,
        permissions=("education_statistics",),
        period="day",
        selected_date="2026-08-04",
    )

    assert report.student_finance.calculated == 100
    assert report.teacher_finance.calculated == 100
    assert report.education.attendance_percent == 100


async def test_report_is_business_scoped_direction_guarded_and_permissioned(
    education_statistics_context,
):
    service, _engine = education_statistics_context

    foreign = await service.report(
        business_account_id=2,
        permissions=None,
        period="month",
        selected_date="2026-08-04",
    )
    assert foreign.education.active_students == 1
    assert foreign.student_finance.paid == 900_000
    assert foreign.result.other_expenses == 999_999

    with pytest.raises(ApiError) as forbidden:
        await service.report(
            business_account_id=1,
            permissions=("education_attendance",),
            period="month",
            selected_date="2026-08-04",
        )
    assert forbidden.value.code == "staff_permission_required"

    with pytest.raises(ApiError) as wrong_direction:
        await service.report(
            business_account_id=3,
            permissions=None,
            period="month",
            selected_date="2026-08-04",
        )
    assert wrong_direction.value.code == "education_direction_required"


async def test_period_validation_and_navigation_match_v1656(
    education_statistics_context,
):
    service, _engine = education_statistics_context

    assert service.shift("day", "2026-08-04", -1) == "2026-08-03"
    assert service.shift("month", "2026-08-04", 1) == "2026-09-01"
    assert service.shift("year", "2026-08-04", -1) == "2025-01-01"

    with pytest.raises(ApiError) as bad_period:
        await service.report(
            business_account_id=1,
            permissions=None,
            period="week",
            selected_date="2026-08-04",
        )
    assert bad_period.value.code == "education_statistics_period_invalid"

    with pytest.raises(ApiError) as bad_date:
        await service.report(
            business_account_id=1,
            permissions=None,
            period="month",
            selected_date="noto'g'ri",
        )
    assert bad_date.value.code == "education_statistics_date_invalid"
