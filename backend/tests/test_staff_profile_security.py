from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.accounts.model import AccountType
from app.auth.dependencies import CurrentAccount
from app.profiles import router as profiles_router
from app.profiles.schemas import BusinessProfileRead


async def test_staff_business_profile_drops_private_owner_fields_and_ungranted_rows(
    monkeypatch,
):
    payload = {
        "sales": [{"id": 1, "total": 50_000}],
        "expenses": [{"id": 2, "amount": 10_000}],
        "orders": [{"id": 3, "phone": "+998900000000"}],
        "staff": [{"id": 11, "name": "Boshqa xodim"}],
    }
    monkeypatch.setattr(
        profiles_router,
        "assembled_cabinet_payload",
        AsyncMock(return_value=payload),
    )
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        r2=SimpleNamespace(create_download_url=lambda key: f"https://media/{key}"),
    )))
    profile = BusinessProfileRead(
        account_id=7,
        name="Turon",
        phone="+998901234567",
        description="",
        public_username="turon",
        direction="Savdo",
        activity_type="Do‘kon",
        address="Qumqo‘rg‘on",
        latitude=None,
        longitude=None,
        work_hours={},
        pay_card="8600000000000000",
        pay_holder="OWNER NAME",
        pay_qr_object_key="private/business/7/payment_qr/qr.png",
        director="Owner",
        tax_id="123456789",
        logo_object_key="private/business/7/logo/logo.png",
        logo_x=50,
        logo_y=50,
        logo_zoom=1,
        dashboard_snapshot={"revenue": 50_000},
        recent_activity=[{
            "id": 3,
            "kind": "order",
            "title": "Maxfiy buyurtma",
            "status": "new",
            "amount": 50_000,
            "created_at": 1,
        }],
        cabinet_payload=payload,
    )
    current = CurrentAccount(
        account_id=7,
        account_type=AccountType.BUSINESS,
        session_token="staff-token",
        actor_type="staff",
        staff_id=11,
        permissions=("kassa",),
    )

    result = await profiles_router.business_profile_response(
        request,
        object(),
        profile,
        current=current,
    )

    assert result.cabinet_payload == {"sales": payload["sales"]}
    assert result.dashboard_snapshot == {}
    assert result.recent_activity == []
    assert result.pay_card == ""
    assert result.pay_holder == ""
    assert result.pay_qr_object_key == ""
    assert result.pay_qr_url == ""
    assert result.director == ""
    assert result.tax_id == ""
