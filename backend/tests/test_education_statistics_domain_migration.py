from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from app.education.model import (
    EducationAttendance,
    EducationGroup,
    EducationPayment,
    EducationStudent,
    EducationTeacher,
    EducationTeacherPayment,
)
from app.education.router import router as education_router


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/migrations/versions/0021_education_statistics.py"
MAIN = ROOT / "backend/app/main.py"


def load_migration():
    spec = spec_from_file_location("education_statistics", MIGRATION)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_migration_normalizes_every_v1656_statistics_source():
    migration = load_migration()

    assert migration.revision == "0021_education_statistics"
    assert migration.down_revision == "0020_statistics_query_indexes"
    source = MIGRATION.read_text(encoding="utf-8")
    for table in (
        "education_attendance",
        "education_payments",
        "education_teachers",
        "education_teacher_payments",
    ):
        assert f'"{table}"' in source
    for resource in (
        "education_groups",
        "education_students",
        "education_attendance",
        "education_payments",
        "education_teachers",
        "education_teacher_payments",
    ):
        assert resource in source
    assert "ON CONFLICT (business_account_id, legacy_source_id)" in source
    assert "ix_education_attendance_business_date" in source
    assert "ix_education_payments_business_created" in source
    assert "ix_education_teacher_payments_business_created" in source


def test_models_preserve_v1656_billing_attendance_and_payroll_fields():
    group_columns = EducationGroup.__table__.columns
    student_columns = EducationStudent.__table__.columns

    for name in (
        "legacy_teacher_id", "teacher_name", "room_name", "capacity",
        "weekdays", "lesson_from", "lesson_to", "start_date", "end_date",
        "billing_type", "package_lessons", "package_price",
    ):
        assert name in group_columns
    for name in (
        "parent_name", "parent_phone", "birth_date", "payment_start_date",
        "lesson_package_override",
    ):
        assert name in student_columns
    assert EducationAttendance.__tablename__ == "education_attendance"
    assert EducationPayment.__tablename__ == "education_payments"
    assert EducationTeacher.__tablename__ == "education_teachers"
    assert EducationTeacherPayment.__tablename__ == "education_teacher_payments"


def test_typed_education_statistics_api_is_wired_into_the_application():
    routes = {
        (route.path, method)
        for route in education_router.routes
        for method in (route.methods or set())
    }
    assert ("/api/v1/education/statistics", "GET") in routes

    source = MAIN.read_text(encoding="utf-8")
    assert "app.state.education_statistics_service = EducationStatisticsService(" in source
