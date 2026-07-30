from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_session_without_cookie_returns_401_not_500():
    app = create_app(Settings(environment="test"))
    client = TestClient(app)

    response = client.get("/api/v1/auth/session")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"
