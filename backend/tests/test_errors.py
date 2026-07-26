from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.errors import ApiError
from app.core.config import Settings
from app.main import create_app


def test_api_error_has_safe_uzbek_message_and_request_id():
    app = create_app(Settings(environment="test"))
    router = APIRouter()

    @router.get("/explode")
    async def explode():
        raise ApiError(409, "duplicate_request", "Bu so‘rov oldin bajarilgan.")

    app.include_router(router)
    response = TestClient(app).get(
        "/explode",
        headers={"X-Request-Id": "req-test-123"},
    )
    assert response.status_code == 409
    assert response.headers["X-Request-Id"] == "req-test-123"
    assert response.json() == {
        "code": "duplicate_request",
        "message": "Bu so‘rov oldin bajarilgan.",
        "request_id": "req-test-123",
    }
