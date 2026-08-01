from datetime import UTC, datetime, time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.advertisements.repository import (
    daily_window_active,
    select_active_advertisements,
    target_specificity,
)
from app.advertisements.schemas import PublicAdvertisement
from app.core.config import Settings
from app.main import create_app


class FakeScalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeSession:
    def __init__(self, values):
        self.values = values

    async def scalars(self, statement):
        return FakeScalars(self.values)


def ad(ad_id, title, targets, **changes):
    values = {
        "id": ad_id,
        "title": title,
        "caption": "",
        "owner_user_account_id": None,
        "owner_business_account_id": None,
        "desktop_image_object_key": "desktop.webp",
        "mobile_image_object_key": "mobile.webp",
        "crop_x": 50.0,
        "crop_y": 50.0,
        "crop_zoom": 1.0,
        "daily_all_day": True,
        "daily_start": None,
        "daily_end": None,
        "targets_json": targets,
        "start_at": datetime(2026, 7, 29, 10, tzinfo=UTC),
    }
    values.update(changes)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_ad_target_precedence_is_district_region_republic():
    session = FakeSession(
        [
            ad(3, "Respublika banneri", []),
            ad(
                2,
                "Viloyat banneri",
                [{"region": "Surxondaryo"}],
            ),
            ad(
                1,
                "Tuman banneri",
                [
                    {
                        "region": "Surxondaryo",
                        "district": "Qumqo‘rg‘on",
                    }
                ],
            ),
            ad(4, "Boshqa tuman", [{"district": "Termiz"}]),
        ]
    )

    items = await select_active_advertisements(
        session,
        now=datetime(2026, 7, 29, 18, 30, tzinfo=UTC),
        placement="home",
        region="Surxondaryo",
        district="Qumqo‘rg‘on",
        image_url_provider=lambda key: f"/media/{key}",
    )

    assert [item.title for item in items] == [
        "Tuman banneri",
        "Viloyat banneri",
        "Respublika banneri",
    ]
    assert items[0].desktop_image_url == "/media/desktop.webp"
    assert items[0].mobile_image_url == "/media/mobile.webp"


def test_daily_window_covers_all_day_boundaries_and_overnight():
    assert daily_window_active(time(12), True, None, None)
    assert daily_window_active(time(18), False, time(18), time(19))
    assert not daily_window_active(time(19), False, time(18), time(19))
    assert daily_window_active(time(23), False, time(22), time(2))
    assert daily_window_active(time(1), False, time(22), time(2))
    assert not daily_window_active(time(3), False, time(22), time(2))


def test_target_specificity_requires_location_match():
    assert target_specificity([], "Surxondaryo", "Qumqo‘rg‘on") == 0
    assert (
        target_specificity(
            [{"region": "Surxondaryo"}],
            "Surxondaryo",
            "Qumqo‘rg‘on",
        )
        == 1
    )
    assert (
        target_specificity(
            [{"region": "Buxoro"}],
            "Surxondaryo",
            "Qumqo‘rg‘on",
        )
        is None
    )


class FakeAdvertisementService:
    def __init__(self):
        self.view_ids = []
        self.click_id = ""

    async def list_public(self, **kwargs):
        return [
            PublicAdvertisement(
                public_id="a_public",
                title="Turon Savdo",
                desktop_image_url="/media/desktop.webp",
                mobile_image_url="/media/mobile.webp",
            )
        ]

    async def record_public_views(self, public_ids):
        self.view_ids = public_ids

    async def record_public_click(self, public_id):
        self.click_id = public_id


def test_public_advertisement_response_excludes_internal_billing_fields():
    app = create_app(Settings(environment="test"))
    app.state.advertisement_service = FakeAdvertisementService()

    response = TestClient(app).get(
        "/api/v1/public/advertisements",
        params={
            "placement": "home",
            "region": "Surxondaryo",
            "district": "Qumqo‘rg‘on",
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["title"] == "Turon Savdo"
    for field in ("price", "views", "clicks", "targets_json"):
        assert field not in response.text


def test_public_advertisement_views_and_clicks_use_public_ids():
    app = create_app(Settings(environment="test"))
    service = FakeAdvertisementService()
    app.state.advertisement_service = service
    client = TestClient(app)

    views = client.post(
        "/api/v1/public/advertisements/views",
        json={"ids": ["a_0123456789abcdef", "a_fedcba9876543210"]},
    )
    click = client.post(
        "/api/v1/public/advertisements/a_0123456789abcdef/click"
    )

    assert views.status_code == 204
    assert click.status_code == 204
    assert service.view_ids == [
        "a_0123456789abcdef",
        "a_fedcba9876543210",
    ]
    assert service.click_id == "a_0123456789abcdef"


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/v1/public/advertisements/views", {"ids": ["a_invalid"]}),
        ("/api/v1/public/advertisements/a_invalid/click", None),
    ],
)
def test_public_advertisement_metrics_reject_invalid_public_ids(path, body):
    app = create_app(Settings(environment="test"))
    app.state.advertisement_service = FakeAdvertisementService()
    client = TestClient(app)

    response = client.post(path, json=body) if body else client.post(path)

    assert response.status_code == 422
