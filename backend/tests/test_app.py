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
