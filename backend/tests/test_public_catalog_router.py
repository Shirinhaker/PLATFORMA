from fastapi.testclient import TestClient

from app.catalog.schemas import (
    PublicCatalogItem,
    PublicCatalogResponse,
)
from app.core.config import Settings
from app.main import create_app


class FakeCatalogService:
    def __init__(self):
        self.params = None

    async def list_items(self, params):
        self.params = params
        return PublicCatalogResponse(
            items=[
                PublicCatalogItem(
                    kind="product",
                    public_id="p_public",
                    name="Mebel",
                    owner_state="unlinked",
                    owner_label="Egasi hali akkauntini bog‘lamagan",
                    can_order=False,
                    can_chat=False,
                )
            ],
            page=params.page,
            page_size=params.page_size,
            total=1,
        )

    async def get_item(self, public_id):
        return PublicCatalogItem(
            kind="product",
            public_id=public_id,
            name="Mebel",
            owner_state="unlinked",
            owner_label="Egasi hali akkauntini bog‘lamagan",
            can_order=False,
            can_chat=False,
        )


def test_catalog_is_hidden_when_phase3c_public_flag_is_disabled():
    app = create_app(Settings(environment="test"))

    response = TestClient(app).get("/api/v1/public/catalog/items")

    assert response.status_code == 404
    assert response.json()["code"] == "feature_not_available"


def test_catalog_route_is_public_and_filters_product():
    app = create_app(
        Settings(environment="test", phase3c_public_enabled=True)
    )
    service = FakeCatalogService()
    app.state.catalog_service = service

    response = TestClient(app).get(
        "/api/v1/public/catalog/items",
        params={"kind": "product", "district": "Qumqo‘rg‘on", "page": 1},
    )

    assert response.status_code == 200
    assert service.params.kind == "product"
    assert service.params.district == "Qumqo‘rg‘on"
    assert all(
        item["kind"] == "product"
        for item in response.json()["items"]
    )
    assert "business_account_id" not in response.text
    assert "image_object_key" not in response.text


def test_catalog_detail_returns_public_projection():
    app = create_app(
        Settings(environment="test", phase3c_public_enabled=True)
    )
    app.state.catalog_service = FakeCatalogService()

    response = TestClient(app).get(
        "/api/v1/public/catalog/items/p_public"
    )

    assert response.status_code == 200
    assert response.json()["public_id"] == "p_public"
