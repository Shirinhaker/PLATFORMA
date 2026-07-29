from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_listings_remain_closed():
    app = create_app(Settings(environment="test", listings_enabled=False))

    response = TestClient(app).get("/api/v1/public/listings")

    assert response.status_code == 404
    assert response.json()["code"] == "feature_not_available"


def test_disabled_listings_does_not_require_listing_service():
    app = create_app(Settings(environment="test", listings_enabled=False))

    assert not hasattr(app.state, "listing_service")
    response = TestClient(app).get("/api/v1/public/listings")
    assert response.status_code == 404
