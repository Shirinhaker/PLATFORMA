import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


FRONTEND_ORIGIN = (
    "https://frontend-staging-production-6c41.up.railway.app"
)


def settings(environment: str, cors_origins: str = "") -> Settings:
    return Settings(
        environment=environment,
        cors_origins=cors_origins,
        telegram_bot_username="koprik_test_bot",
        telegram_bot_token="test-token",
        telegram_webhook_secret="test-webhook-secret",
        otp_secret="test-otp-secret",
        csrf_secret="test-csrf-secret",
        outbox_encryption_key=(
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        ),
    )


def test_staging_refuses_to_start_without_explicit_cors_origin():
    with pytest.raises(
        RuntimeError,
        match="cors_origins_required_for_deployed_environment",
    ):
        create_app(settings("staging"))


def test_production_refuses_to_start_without_explicit_cors_origin():
    with pytest.raises(
        RuntimeError,
        match="cors_origins_required_for_deployed_environment",
    ):
        create_app(settings("production"))


def test_staging_preflight_allows_the_exact_frontend_origin():
    app = create_app(settings("staging", FRONTEND_ORIGIN))
    client = TestClient(app)

    response = client.options(
        "/api/v1/auth/session",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"


def test_staging_does_not_allow_an_unlisted_railway_origin():
    app = create_app(settings("staging", FRONTEND_ORIGIN))
    client = TestClient(app)

    response = client.options(
        "/api/v1/auth/session",
        headers={
            "Origin": "https://unlisted-web.up.railway.app",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
