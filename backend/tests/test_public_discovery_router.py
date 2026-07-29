from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.public_discovery.schemas import (
    PublicSearchItem,
    PublicSearchResponse,
)


class FakePublicDiscoveryService:
    def __init__(self, *, content=False):
        self.params = None
        self.content = content

    async def search(self, params):
        self.params = params
        if self.content:
            items = [
                PublicSearchItem(
                    kind="product",
                    public_id="p_public",
                    name="Mebel",
                    price_text="Kelishiladi",
                    owner_state="unlinked",
                    owner_label="Egasi hali akkauntini bog‘lamagan",
                    can_order=False,
                    can_chat=False,
                )
            ]
        else:
            items = [
                PublicSearchItem(
                    kind="business",
                    public_id="b_public",
                    name="Koprik Savdo",
                    direction="Savdo",
                )
            ]
        return PublicSearchResponse(
            items=items,
            page=params.page,
            page_size=params.page_size,
            total=1,
        )


def test_public_search_is_unauthenticated_and_returns_only_public_fields():
    app = create_app(Settings(environment="test"))
    service = FakePublicDiscoveryService()
    app.state.public_discovery_service = service

    response = TestClient(app).get(
        "/api/v1/public/search",
        params={
            "q": "savdo",
            "result_type": "business",
            "page": 2,
            "page_size": 10,
        },
    )

    assert response.status_code == 200
    assert service.params.q == "savdo"
    assert service.params.page == 2
    assert response.json() == {
        "items": [
            {
                "kind": "business",
                "public_id": "b_public",
                "name": "Koprik Savdo",
                "public_username": "",
                "description": "",
                "direction": "Savdo",
                "activity_type": "",
                "region": "",
                "district": "",
                "mahalla": "",
                "image_url": "",
            }
        ],
        "page": 2,
        "page_size": 10,
        "total": 1,
        "pages": 1,
    }


def test_public_search_rejects_oversized_pages():
    app = create_app(Settings(environment="test"))
    app.state.public_discovery_service = FakePublicDiscoveryService()

    response = TestClient(app).get(
        "/api/v1/public/search",
        params={"page_size": 51},
    )

    assert response.status_code == 422


def test_product_search_returns_only_content_capability_fields():
    app = create_app(Settings(environment="test"))
    app.state.public_discovery_service = FakePublicDiscoveryService(
        content=True
    )

    response = TestClient(app).get(
        "/api/v1/public/search",
        params={"result_type": "product"},
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["kind"] == "product"
    assert item["owner_state"] == "unlinked"
    assert item["can_order"] is False
    assert "business_account_id" not in item
