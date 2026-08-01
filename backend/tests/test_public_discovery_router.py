from fastapi.testclient import TestClient

from app.accounts.model import AccountType
from app.auth.dependencies import CurrentAccount, require_current_account
from app.core.config import Settings
from app.main import create_app
from app.public_discovery.router import optional_current_account
from app.public_discovery.schemas import (
    PublicSearchItem,
    PublicSearchResponse,
    PublicFollowedProfile,
    PublicProfileDetail,
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

    async def home_map(self, district, *, account_id=None, account_type=None):
        self.home_map_district = district
        self.home_map_actor = (account_id, account_type)
        return {
            "businesses": [{
                "id": 41,
                "public_id": "b_public",
                "name": "Koprik Savdo",
                "yon": "Savdo",
                "tur": "Do‘kon",
                "lat": 37.82,
                "lng": 67.58,
                "logo_file": "",
                "logo_x": 50,
                "logo_y": 50,
                "logo_zoom": 1,
                "address": "Qumqo‘rg‘on",
                "source": "public",
            }],
            "specialists": [],
        }

    async def district_offers(self, district):
        self.offers_district = district
        return {
            "needs_district": False,
            "slot": 1,
            "items": [],
        }

    async def followed_profiles(self, *, account_id, account_type):
        self.followed_actor = (account_id, account_type)
        return [
            PublicFollowedProfile(
                kind="business",
                public_id="b_public",
                name="Koprik Savdo",
            )
        ]

    async def profile(self, *, kind, public_id):
        self.profile_target = (kind, public_id)
        return PublicProfileDetail(
            kind=kind,
            public_id=public_id,
            name="Koprik Savdo",
            direction="Savdo",
            activity_type="Do‘kon",
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


def test_public_home_map_and_district_offers_match_v1656_contract():
    app = create_app(Settings(environment="test"))
    service = FakePublicDiscoveryService()
    app.state.public_discovery_service = service
    client = TestClient(app)

    map_response = client.get(
        "/api/v1/public/home/map",
        params={"district": " Qumqo‘rg‘on "},
    )
    offers_response = client.get(
        "/api/v1/public/home/district-offers",
        params={"district": " Qumqo‘rg‘on "},
    )

    assert map_response.status_code == 200
    assert map_response.json()["businesses"][0]["public_id"] == "b_public"
    assert offers_response.status_code == 200
    assert offers_response.json()["needs_district"] is False
    assert service.home_map_district == "Qumqo‘rg‘on"
    assert service.home_map_actor == (None, None)
    assert service.offers_district == "Qumqo‘rg‘on"


def test_public_features_expose_server_flags_without_authentication():
    app = create_app(Settings(
        environment="test",
        listings_enabled=True,
    ))

    response = TestClient(app).get("/api/v1/public/features")

    assert response.status_code == 200
    assert response.json() == {
        "listings": True,
        "stories": False,
        "chat": False,
        "systemization": False,
        "taxi": False,
    }


def test_followed_profiles_require_and_use_the_active_actor():
    app = create_app(Settings(environment="test"))
    service = FakePublicDiscoveryService()
    app.state.public_discovery_service = service
    app.dependency_overrides[require_current_account] = lambda: CurrentAccount(
        account_id=71,
        account_type=AccountType.USER,
        session_token="test-session",
    )

    response = TestClient(app).get(
        "/api/v1/public/home/followed-profiles"
    )

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Koprik Savdo"
    assert service.followed_actor == (71, "user")


def test_public_home_map_uses_the_optional_active_actor():
    app = create_app(Settings(environment="test"))
    service = FakePublicDiscoveryService()
    app.state.public_discovery_service = service
    app.dependency_overrides[optional_current_account] = lambda: CurrentAccount(
        account_id=71,
        account_type=AccountType.USER,
        session_token="test-session",
    )

    response = TestClient(app).get(
        "/api/v1/public/home/map",
        params={"district": "Qumqo‘rg‘on"},
    )

    assert response.status_code == 200
    assert service.home_map_actor == (71, "user")


def test_public_profile_opens_from_its_safe_public_id():
    app = create_app(Settings(environment="test"))
    service = FakePublicDiscoveryService()
    app.state.public_discovery_service = service
    public_id = "b_0123456789abcdef"

    response = TestClient(app).get(
        f"/api/v1/public/profiles/business/{public_id}"
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Koprik Savdo"
    assert service.profile_target == ("business", public_id)
