from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_healthz_is_process_only():
    app = create_app(Settings(environment="test"))
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "koprik-api",
        "environment": "test",
    }


def test_v1_build_identifies_foundation_without_changing_legacy_build():
    app = create_app(Settings(environment="test"))
    response = TestClient(app).get("/api/v1/build")
    assert response.status_code == 200
    assert response.json() == {
        "api_version": "v1",
        "foundation": "phase1",
        "legacy_build": "v1656",
    }


def test_cors_allows_only_the_configured_frontend_origin():
    origin = "https://frontend-staging.up.railway.app"
    app = create_app(
        Settings(environment="test", cors_origins=origin)
    )
    client = TestClient(app)

    preflight = client.options(
        "/api/v1/build",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["Access-Control-Allow-Origin"] == origin
    assert preflight.headers["Access-Control-Allow-Credentials"] == "true"

    unknown = client.get(
        "/api/v1/build",
        headers={"Origin": "https://unknown.example"},
    )
    assert unknown.status_code == 200
    assert "Access-Control-Allow-Origin" not in unknown.headers


def test_cors_is_disabled_when_no_origin_is_configured():
    app = create_app(Settings(environment="test", cors_origins=""))
    response = TestClient(app).get(
        "/api/v1/build",
        headers={"Origin": "https://frontend-staging.up.railway.app"},
    )

    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers
