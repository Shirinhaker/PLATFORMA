from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.accounts.model import AccountType
from app.auth.schemas import SessionIdentity
from app.auth.security import derive_csrf
from app.core.config import Settings
from app.main import create_app


class FakeAuthService:
    def __init__(self, identities):
        self.identities = identities

    async def resolve_session(self, raw_token, now):
        return self.identities.get(raw_token)


@pytest.fixture
async def online_clients():
    settings = Settings(
        environment="test",
        csrf_secret="online-csrf-secret",
    )
    now = datetime.now(UTC)
    identities = {
        "business-token": SessionIdentity(
            account_id=7,
            account_type=AccountType.BUSINESS,
            login="muhr1",
            csrf_token=derive_csrf(
                "business-token",
                settings.csrf_secret,
            ),
            expires_at=now + timedelta(days=1),
        ),
        "user-token": SessionIdentity(
            account_id=5,
            account_type=AccountType.USER,
            login="user1",
            csrf_token=derive_csrf(
                "user-token",
                settings.csrf_secret,
            ),
            expires_at=now + timedelta(days=1),
        ),
    }
    service = SimpleNamespace(
        read_resource=AsyncMock(return_value=[{"id": 1, "name": "Muhr"}]),
        create_record=AsyncMock(return_value=(
            {"id": 2, "name": "Yangi"},
            [{"id": 2, "name": "Yangi"}],
        )),
        patch_record=AsyncMock(),
        delete_record=AsyncMock(),
        apply_action=AsyncMock(return_value=(
            None,
            [{"id": 7, "is_read": 1}],
        )),
    )
    profile_summary = SimpleNamespace(invalidate=AsyncMock())
    app = create_app(settings)
    app.state.auth_service = FakeAuthService(identities)
    app.state.business_online_service = service
    app.state.profile_summary_service = profile_summary

    transport = httpx.ASGITransport(app=app)
    async with (
        httpx.AsyncClient(
            transport=transport,
            base_url="https://api.test",
        ) as business,
        httpx.AsyncClient(
            transport=transport,
            base_url="https://api.test",
        ) as user,
    ):
        business.cookies.set(
            settings.auth_cookie_name,
            "business-token",
            domain="api.test",
            path="/",
        )
        user.cookies.set(
            settings.auth_cookie_name,
            "user-token",
            domain="api.test",
            path="/",
        )
        yield SimpleNamespace(
            business=business,
            user=user,
            service=service,
            profile_summary=profile_summary,
            business_csrf=derive_csrf(
                "business-token",
                settings.csrf_secret,
            ),
        )


async def test_user_cannot_read_business_online_resource(online_clients):
    response = await online_clients.user.get("/api/v1/business-online/items")

    assert response.status_code == 403
    assert response.json()["code"] == "business_online_forbidden"
    online_clients.service.read_resource.assert_not_awaited()


async def test_business_online_mutation_requires_csrf(online_clients):
    response = await online_clients.business.post(
        "/api/v1/business-online/items",
        json={"record": {"name": "Yangi"}},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"
    online_clients.service.create_record.assert_not_awaited()


async def test_business_action_uses_current_account_and_invalidates_summary(
    online_clients,
):
    response = await online_clients.business.post(
        "/api/v1/business-online/notifications/actions/mark_all_read",
        headers={"X-CSRF-Token": online_clients.business_csrf},
        json={"payload": {}},
    )

    assert response.status_code == 200, response.text
    online_clients.service.apply_action.assert_awaited_once_with(
        7,
        "notifications",
        "mark_all_read",
        record_id=None,
        data={},
    )
    online_clients.profile_summary.invalidate.assert_awaited_once_with(
        AccountType.BUSINESS,
        7,
    )
