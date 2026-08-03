import pytest
from pydantic import ValidationError

from app.accounts.model import AccountType
from app.auth.dependencies import (
    CurrentAccount,
    require_business_owner,
    require_staff_permission,
)
from app.core.errors import ApiError
from app.orders.router import staff_order_categories
from app.profiles import router as profiles_router
from app.profiles.schemas import CabinetSwitchRequest
from app.staff.permissions import (
    allowed_payload_resources,
    clean_permissions,
    permission_definitions,
    permission_templates,
)
from app.staff.schemas import StaffMemberPatch


def current(*, actor: str = "staff", permissions: tuple[str, ...] = ()):
    return CurrentAccount(
        account_id=7,
        account_type=AccountType.BUSINESS,
        session_token="token",
        actor_type=actor,
        staff_id=11 if actor == "staff" else None,
        permissions=permissions,
    )


def test_direction_permissions_match_v1656_templates_and_drop_unknown_values():
    definitions = permission_definitions("Savdo")
    templates = permission_templates("Savdo")

    assert {item.key for item in definitions} >= {
        "items", "buyurtma", "kassa", "ombor", "expenses", "debts",
        "chats", "notifications", "ads", "documents",
    }
    assert next(item for item in templates if item.key == "cashier").permissions == (
        "buyurtma", "kassa", "debts",
    )
    assert clean_permissions(["kassa", "unknown", "kassa"], "Savdo") == ["kassa"]


def test_staff_permission_and_owner_boundaries_are_server_enforced():
    require_staff_permission(current(permissions=("kassa",)), "kassa")
    require_staff_permission(current(actor="owner"), "anything")

    with pytest.raises(ApiError) as denied:
        require_staff_permission(current(permissions=("debts",)), "kassa")
    assert denied.value.code == "staff_permission_required"

    with pytest.raises(ApiError) as owner_only:
        require_business_owner(current(permissions=("kassa",)))
    assert owner_only.value.code == "business_owner_required"


async def test_cabinet_switch_allows_account_owner_but_rejects_staff_actor():
    user_owner = CurrentAccount(
        account_id=7,
        account_type=AccountType.USER,
        session_token="owner-token",
    )
    with pytest.raises(ApiError) as already_active:
        await profiles_router.switch_cabinet(
            CabinetSwitchRequest(target_type=AccountType.USER),
            object(),
            object(),
            user_owner,
            object(),
        )
    assert already_active.value.code == "cabinet_already_active"

    with pytest.raises(ApiError) as staff_denied:
        await profiles_router.switch_cabinet(
            CabinetSwitchRequest(target_type=AccountType.BUSINESS),
            object(),
            object(),
            current(),
            object(),
        )
    assert staff_denied.value.code == "staff_permission_required"


def test_staff_profile_payload_is_limited_to_granted_resources():
    allowed = allowed_payload_resources(("kassa", "documents"))

    assert {"sales", "cash_transactions", "documents"} <= allowed
    assert "staff" not in allowed
    assert "orders" not in allowed
    assert "expenses" not in allowed
    assert "warehouse_items" not in allowed


def test_staff_order_permissions_are_split_by_server_side_category():
    assert staff_order_categories(current(permissions=("service_orders",))) == frozenset({
        "service"
    })
    assert staff_order_categories(current(permissions=("buyurtma",))) == frozenset({
        "product"
    })
    assert staff_order_categories(current(
        permissions=("buyurtma", "service_orders"),
    )) == frozenset({"product", "service"})
    assert staff_order_categories(current(actor="owner")) is None


def test_staff_patch_rejects_null_for_non_nullable_database_fields():
    with pytest.raises(ValidationError):
        StaffMemberPatch(name=None)
    with pytest.raises(ValidationError):
        StaffMemberPatch(salary=None)
    assert StaffMemberPatch(hire_date=None).model_fields_set == {"hire_date"}
