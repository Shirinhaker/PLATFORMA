from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_taxi_public_entry_points_follow_the_typed_feature_flag():
    closed = create_app(Settings(environment="test", taxi_enabled=False))
    opened = create_app(Settings(environment="test", taxi_enabled=True))

    assert TestClient(closed).get("/api/v1/public/features").json()["taxi"] is False
    assert TestClient(opened).get("/api/v1/public/features").json()["taxi"] is True
