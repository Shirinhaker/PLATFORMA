"""To'lovni faqat admin tasdiqlashi mumkin.

Ilgari `POST /api/v1/payments/{id}/approve` mavjud edi va uni
`require_business_owner` himoya qilardi — ya'ni **har qanday biznes
egasi o'zining to'lovini o'zi tasdiqlab** bepul obuna olardi. Endi
qaror faqat `/api/v1/admin/...` ostida, alohida admin sessiyasi bilan.
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.accounts.model import AccountType
from app.core.config import Settings
from app.main import create_app
from app.payments.schemas import PaymentRequestRead


ADMIN_TG = 1423181561
BUSINESS_ACCOUNT = 7


def _settings() -> Settings:
    return Settings(
        environment="test",
        telegram_bot_username="koprik_test_bot",
        otp_secret="test-otp-secret",
        csrf_secret="test-csrf-secret",
        outbox_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        admin_telegram_ids=str(ADMIN_TG),
    )


class FakeAuthService:
    """Biznes egasining oddiy sessiyasi."""

    async def resolve_session(self, token: str):
        if token != "business-token":
            return None
        return SimpleNamespace(
            account_id=BUSINESS_ACCOUNT,
            account_type=AccountType.BUSINESS,
            session_token=token,
            actor_type="owner",
            staff_id=None,
            permissions=(),
        )

    async def issue_csrf(self, token: str) -> str:
        return "csrf-token"

    def verify_csrf(self, session_token: str, csrf_token: str) -> bool:
        return csrf_token == "csrf-token"


@pytest.fixture
async def api():
    settings = _settings()
    app = create_app(settings)
    app.state.auth_service = FakeAuthService()
    # Admin sessiyasi ochilmagan: hech qanday token tan olinmaydi.
    app.state.admin_auth_service = SimpleNamespace(
        resolve=AsyncMock(return_value=None),
    )
    app.state.payment_service = SimpleNamespace(
        review=AsyncMock(return_value=PaymentRequestRead(
            id=1,
            request_code="PAY-TEST",
            service_type="subscription",
            status="approved",
            plan_code="plus",
            duration_months=1,
            quantity=1,
            amount=99000,
            currency="UZS",
            price_code="subscription_plus_1m",
            public_reason="",
            created_at=1785200000,
            updated_at=1785200000,
            attempts=[],
        )),
    )
    app.state.admin_payment_service = SimpleNamespace(
        list_payments=AsyncMock(return_value=[]),
        detail=AsyncMock(),
        receipt_link=AsyncMock(),
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="https://api.test"
    ) as client:
        client.cookies.set(
            settings.auth_cookie_name,
            "business-token",
            domain="api.test",
            path="/",
        )
        yield SimpleNamespace(client=client, app=app)


async def test_business_approval_endpoint_no_longer_exists(api):
    """Eski teshik: biznes egasi o'z to'lovini tasdiqlashi."""
    for path in (
        "/api/v1/payments/1/approve",
        "/api/v1/payments/1/reject",
    ):
        response = await api.client.post(
            path,
            json={"reason": "o‘zim to‘ladim"},
            headers={"X-CSRF-Token": "csrf-token"},
        )
        assert response.status_code == 404, path
    api.app.state.payment_service.review.assert_not_awaited()


async def test_admin_endpoints_reject_a_plain_business_session(api):
    """Biznes cookie'si admin bo'limlarini ochmaydi."""
    for method, path in (
        ("post", "/api/v1/admin/payments/1/approve"),
        ("post", "/api/v1/admin/payments/1/reject"),
        ("post", "/api/v1/admin/payments/1/cancel"),
        ("get", "/api/v1/admin/payments"),
        ("get", "/api/v1/admin/payments/1"),
        ("get", "/api/v1/admin/payments/1/receipt"),
        ("get", "/api/v1/admin/prices"),
        ("get", "/api/v1/admin/payment-methods"),
    ):
        call = getattr(api.client, method)
        response = await (
            call(path, json={"reason": "", "internal_note": ""})
            if method == "post"
            else call(path)
        )
        assert response.status_code == 401, path
        assert response.json()["code"] == "admin_session_required"
    api.app.state.payment_service.review.assert_not_awaited()
    api.app.state.admin_payment_service.list_payments.assert_not_awaited()


async def test_admin_session_cookie_is_separate_from_the_user_one(api):
    """Admin tokeni oddiy sessiya cookie'siga qo'yilsa ishlamaydi."""
    settings = api.app.state.settings
    assert settings.admin_cookie_name != settings.auth_cookie_name

    async def resolve(token: str):
        return ADMIN_TG if token == "admin-token" else None

    api.app.state.admin_auth_service.resolve = resolve

    # Haqiqiy admin tokeni, lekin noto'g'ri cookie'da.
    api.client.cookies.set(
        settings.auth_cookie_name,
        "admin-token",
        domain="api.test",
        path="/",
    )
    blocked = await api.client.get("/api/v1/admin/payments")
    assert blocked.status_code == 401
    api.app.state.admin_payment_service.list_payments.assert_not_awaited()

    # O'sha token admin cookie'sida bo'lsa ochiladi.
    api.client.cookies.set(
        settings.admin_cookie_name,
        "admin-token",
        domain="api.test",
        path="/",
    )
    allowed = await api.client.get("/api/v1/admin/payments")
    assert allowed.status_code == 200


async def test_admin_session_unlocks_the_queue(api):
    """Haqiqiy admin sessiyasi bilan navbat ochiladi."""
    api.app.state.admin_auth_service.resolve = AsyncMock(return_value=ADMIN_TG)
    api.client.cookies.set(
        api.app.state.settings.admin_cookie_name,
        "admin-token",
        domain="api.test",
        path="/",
    )

    response = await api.client.get("/api/v1/admin/payments")
    assert response.status_code == 200
    api.app.state.admin_payment_service.list_payments.assert_awaited_once()

    decision = await api.client.post(
        "/api/v1/admin/payments/1/approve",
        json={"reason": "", "internal_note": "chek to‘g‘ri"},
    )
    assert decision.status_code == 200
    call = api.app.state.payment_service.review.await_args.kwargs
    assert call["admin_telegram_id"] == ADMIN_TG
    assert call["decision"] == "approved"


async def test_admin_auth_start_refuses_unlisted_id(api):
    """Ro'yxatda yo'q Telegram ID uchun kod yuborilmaydi."""
    api.app.state.admin_auth_service = SimpleNamespace(
        resolve=AsyncMock(return_value=None),
        start=AsyncMock(side_effect=AssertionError("chaqirilmasligi kerak")),
    )
    from app.admin.service import AdminAuthService

    real = AdminAuthService(
        _unused_session_factory(), _settings(), now_provider=lambda: None
    )
    assert real.is_admin(ADMIN_TG) is True
    assert real.is_admin(999) is False


def _unused_session_factory():
    @asynccontextmanager
    async def factory():
        raise AssertionError("sessiya ochilmasligi kerak")
        yield None

    return factory
