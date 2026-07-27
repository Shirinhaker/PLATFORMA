from datetime import UTC, datetime, timedelta

import fakeredis.aioredis
import httpx
import pytest

from app.accounts.model import AccountType
from app.auth.schemas import (
    Authenticated,
    ChallengeResent,
    LoginStarted,
    RegistrationStarted,
    SessionIdentity,
)
from app.auth.security import derive_csrf
from app.auth.service import INVALID_CREDENTIALS
from app.core.config import Settings
from app.main import create_app


class FakeAuthService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.sessions: dict[str, SessionIdentity] = {}

    async def start_registration(self, data, now):
        return RegistrationStarted(
            request_id=11,
            deep_link="https://t.me/koprik_test_bot?start=register-token",
            expires_in=600,
            resend_after=60,
        )

    async def verify_registration(self, request_id, code, device_name, now):
        return self._authenticate(
            account_id=11,
            account_type=AccountType.USER,
            login="u_created",
            password="one-time-password",
            now=now,
        )

    async def start_login(self, login, password, now):
        if login.strip().lower() == "missing":
            raise INVALID_CREDENTIALS
        return LoginStarted(
            request_id=22,
            deep_link="https://t.me/koprik_test_bot?start=login-token",
            code_sent=True,
            expires_in=300,
            resend_after=60,
        )

    async def verify_login(self, request_id, code, device_name, now):
        return self._authenticate(
            account_id=22,
            account_type=AccountType.BUSINESS,
            login=None,
            password=None,
            now=now,
        )

    async def resend_challenge(self, request_id, now):
        return ChallengeResent(
            request_id=request_id,
            code_version=2,
            expires_in=300,
            resend_after=60,
        )

    async def resolve_session(self, raw_token, now):
        return self.sessions.get(raw_token)

    async def revoke_session(self, raw_token, now):
        self.sessions.pop(raw_token, None)

    def _authenticate(
        self,
        *,
        account_id,
        account_type,
        login,
        password,
        now,
    ):
        raw_token = f"session-{account_id}"
        csrf_token = derive_csrf(raw_token, self.settings.csrf_secret)
        expires_at = now + timedelta(days=30)
        self.sessions[raw_token] = SessionIdentity(
            account_id=account_id,
            account_type=account_type,
            login=login or "b_demo",
            csrf_token=csrf_token,
            expires_at=expires_at,
        )
        return Authenticated(
            account_id=account_id,
            account_type=account_type,
            session_token=raw_token,
            csrf_token=csrf_token,
            expires_at=expires_at,
            login=login,
            password=password,
        )


@pytest.fixture
async def api_client():
    settings = Settings(
        environment="test",
        csrf_secret="test-csrf-secret",
    )
    app = create_app(settings)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = FakeAuthService(settings)
    app.state.redis = redis
    app.state.auth_service = service
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://api.test",
    ) as client:
        client.auth_service = service
        yield client
    await redis.aclose()


async def test_login_verify_sets_secure_http_only_cookie(api_client):
    response = await api_client.post(
        "/api/v1/auth/login/verify",
        json={"request_id": 22, "code": "123456", "device_name": "pytest"},
    )

    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "koprik_session=" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert response.json()["account_type"] == "business"
    assert response.json()["csrf_token"]
    assert "session_token" not in response.json()


async def test_registration_returns_credentials_once_without_session_token(
    api_client,
):
    response = await api_client.post(
        "/api/v1/auth/register/verify",
        json={"request_id": 11, "code": "123456", "device_name": "pytest"},
    )

    assert response.status_code == 200
    assert response.json()["login"] == "u_created"
    assert response.json()["password"] == "one-time-password"
    assert "session_token" not in response.json()


async def test_login_does_not_accept_account_type(api_client):
    response = await api_client.post(
        "/api/v1/auth/login/start",
        json={
            "login": "u_demo",
            "password": "secret",
            "account_type": "user",
        },
    )
    assert response.status_code == 422


async def test_logout_requires_csrf_and_revokes_session(api_client):
    logged_in = await api_client.post(
        "/api/v1/auth/login/verify",
        json={"request_id": 22, "code": "123456", "device_name": "pytest"},
    )
    csrf = logged_in.json()["csrf_token"]

    denied = await api_client.post("/api/v1/auth/logout")
    assert denied.status_code == 403
    accepted = await api_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf},
    )
    assert accepted.status_code == 204
    restored = await api_client.get("/api/v1/auth/session")
    assert restored.status_code == 401


async def test_session_returns_identity_without_raw_cookie(api_client):
    logged_in = await api_client.post(
        "/api/v1/auth/login/verify",
        json={"request_id": 22, "code": "123456", "device_name": "pytest"},
    )
    response = await api_client.get("/api/v1/auth/session")

    assert response.status_code == 200
    assert response.json()["account_id"] == 22
    assert response.json()["account_type"] == "business"
    assert "session_token" not in response.json()
    assert "session-22" not in response.text
    assert logged_in.cookies["koprik_session"] == "session-22"


async def test_api_error_contains_code_message_and_request_id(api_client):
    response = await api_client.post(
        "/api/v1/auth/login/start",
        headers={"X-Request-Id": "phase2-test"},
        json={"login": "missing", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.json() == {
        "code": "invalid_credentials",
        "message": "Login yoki parol noto‘g‘ri.",
        "request_id": "phase2-test",
    }


async def test_sixth_login_attempt_is_rate_limited(api_client):
    for _ in range(5):
        response = await api_client.post(
            "/api/v1/auth/login/start",
            json={"login": "missing", "password": "wrong"},
        )
        assert response.status_code == 401

    response = await api_client.post(
        "/api/v1/auth/login/start",
        json={"login": "missing", "password": "wrong"},
    )
    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"
    assert int(response.headers["Retry-After"]) >= 1
