from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from app.education.model import EducationPayment
from app.education.router import router as education_router


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/migrations/versions/0034_education_management.py"


def _migration():
    spec = spec_from_file_location("education_management", MIGRATION)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_cash_receipt_link_is_migrated_and_backfilled():
    migration = _migration()
    source = MIGRATION.read_text(encoding="utf-8")
    assert migration.revision == "0034_education_management"
    assert migration.down_revision == "0033_notifications_v1656"
    assert "cash_receipt_id" in EducationPayment.__table__.columns
    assert "fk_education_payments_cash_receipt" in source
    assert "uq_education_payments_cash_receipt" in source
    assert "receipt_line.legacy_source_key = 'sales:'" in source


def test_all_remaining_education_management_routes_are_typed():
    routes = {
        (route.path, method)
        for route in education_router.routes
        for method in (route.methods or set())
    }
    expected = {
        ("/api/v1/education/groups", "GET"),
        ("/api/v1/education/groups", "POST"),
        ("/api/v1/education/groups/{group_id}", "PUT"),
        ("/api/v1/education/groups/{group_id}", "DELETE"),
        ("/api/v1/education/students", "GET"),
        ("/api/v1/education/students", "POST"),
        ("/api/v1/education/students/{student_id}", "PUT"),
        ("/api/v1/education/students/{student_id}", "DELETE"),
        ("/api/v1/education/students/{student_id}/card", "GET"),
        ("/api/v1/education/students/{student_id}/transfer", "POST"),
        ("/api/v1/education/attendance", "GET"),
        ("/api/v1/education/attendance", "PUT"),
        ("/api/v1/education/payment-control", "GET"),
        ("/api/v1/education/payments", "GET"),
        ("/api/v1/education/payments", "POST"),
        ("/api/v1/education/payments/{payment_id}/void", "POST"),
        ("/api/v1/education/teachers", "GET"),
        ("/api/v1/education/teachers", "POST"),
        ("/api/v1/education/teachers/{teacher_id}", "PUT"),
        ("/api/v1/education/teachers/{teacher_id}", "DELETE"),
        ("/api/v1/education/teacher-payroll", "GET"),
        ("/api/v1/education/teacher-payroll", "POST"),
        ("/api/v1/education/teacher-payroll/{payment_id}", "DELETE"),
    }
    assert expected <= routes
