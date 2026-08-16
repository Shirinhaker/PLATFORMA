from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

from app.accounts.model import AccountType
from app.auth.dependencies import CurrentAccount
from app.core.errors import ApiError
from app.payments.router import require_payment_owner
from app.payments.router import router as payments_router

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/migrations/versions/0036_subscription_payments.py"


def _migration():
    spec = spec_from_file_location("subscription_payments", MIGRATION)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_k23_migration_extends_follow_lists_head_with_history_index():
    migration = _migration()
    source = MIGRATION.read_text(encoding="utf-8")

    assert migration.revision == "0036_subscription_payments"
    assert migration.down_revision == "0035_follow_lists"
    assert '["business_account_id", "id"]' in source


def test_payments_router_exposes_typed_subscription_and_payment_reads():
    routes = {
        (route.path, method)
        for route in payments_router.routes
        for method in (route.methods or set())
    }

    assert ("/api/v1/payments/subscription", "GET") in routes
    assert ("/api/v1/payments/my", "GET") in routes


def test_staff_cannot_open_owner_payment_history():
    staff = CurrentAccount(
        account_id=7,
        account_type=AccountType.BUSINESS,
        session_token="staff-token",
        actor_type="staff",
        staff_id=12,
        permissions=("payments",),
    )

    with pytest.raises(ApiError) as error:
        require_payment_owner(staff)

    assert error.value.code == "payment_owner_required"
