from contextlib import asynccontextmanager

import pytest

from app.business_online.service import BusinessOnlineService
from app.core.errors import ApiError
from app.profiles.model import BusinessProfile


class FakeSession:
    def __init__(self, profile: BusinessProfile):
        self.profile = profile
        self.commits = 0

    async def scalar(self, statement):
        return self.profile

    async def get(self, model, account_id):
        if model is BusinessProfile and account_id == self.profile.account_id:
            return self.profile
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None


class FakeDatabase:
    def __init__(self, profile: BusinessProfile):
        self.session_value = FakeSession(profile)

    @asynccontextmanager
    async def session(self):
        yield self.session_value


def business_profile() -> BusinessProfile:
    return BusinessProfile(
        account_id=7,
        name="Muhr",
        phone="912377784",
        description="",
        public_username="muhr1",
        direction="Savdo",
        activity_type="Oziq-ovqat do'koni",
        address="Qumqo‘rg‘on",
        work_hours={},
        pay_card="",
        pay_holder="",
        pay_qr_object_key="",
        director="",
        tax_id="",
        logo_object_key="",
        logo_x=50,
        logo_y=50,
        logo_zoom=1,
        followers_count=1,
        following_count=1,
        rating_sum=5,
        rating_count=1,
        map_visible=True,
        dashboard_snapshot={"new_orders": 1, "unread": 1},
        recent_activity=[],
        cabinet_payload={
            "items": [{"id": 4, "name": "Eski mahsulot", "price": 10000}],
            "orders": [{
                "id": 44,
                "title": "Muhr",
                "status": "new",
                "order_type": "product",
                "total_amount": 15000,
                "created_at": 100,
            }],
            "notifications": [{"id": 7, "title": "Yangi", "is_read": 0}],
            "business_reviews": [{"id": 8, "rating": 5, "text": "Yaxshi"}],
            "followers": [{"id": 9, "name": "Vali"}],
            "following": [{"id": 10, "name": "Hamkor"}],
            "messages": [],
            "listings": [{"id": 11, "title": "E’lon", "status": "active"}],
            "stories": [],
            "advertisements": [],
            "business_subscriptions": [],
            "subscription_payments": [],
            "item_groups": [],
        },
    )


@pytest.mark.asyncio
async def test_create_item_preserves_existing_payload_and_assigns_next_id():
    profile = business_profile()
    database = FakeDatabase(profile)
    service = BusinessOnlineService(database.session)

    item, rows = await service.create_record(
        7,
        "items",
        {"name": "Yangi mahsulot", "price": 20000},
    )

    assert item["id"] == 5
    assert [row["name"] for row in rows] == ["Eski mahsulot", "Yangi mahsulot"]
    assert profile.cabinet_payload["orders"][0]["id"] == 44
    assert database.session_value.commits == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    ["password", "password_hash", "telegram_user_id", "api_token"],
)
async def test_create_rejects_sensitive_identity_fields(field):
    service = BusinessOnlineService(FakeDatabase(business_profile()).session)

    with pytest.raises(ApiError) as error:
        await service.create_record(
            7,
            "items",
            {"name": "Mahsulot", field: "secret"},
        )

    assert error.value.code == "sensitive_record_field"


@pytest.mark.asyncio
async def test_create_drops_ownership_fields_without_overwriting_owner():
    profile = business_profile()
    service = BusinessOnlineService(FakeDatabase(profile).session)

    item, _ = await service.create_record(
        7,
        "items",
        {"name": "Mahsulot", "business_id": 999, "owner_id": 999},
    )

    assert "business_id" not in item
    assert "owner_id" not in item


@pytest.mark.asyncio
async def test_online_actions_update_dashboard_and_keep_nested_order_data():
    profile = business_profile()
    service = BusinessOnlineService(FakeDatabase(profile).session)

    order, orders = await service.apply_action(
        7,
        "orders",
        "set_status",
        record_id=44,
        data={"status": "accepted"},
    )
    assert order is not None
    assert order["status"] == "accepted"
    assert orders[0]["title"] == "Muhr"
    assert profile.dashboard_snapshot["new_orders"] == 0
    assert profile.dashboard_snapshot["active_orders"] == 1

    await service.apply_action(
        7,
        "notifications",
        "mark_all_read",
        record_id=None,
        data={},
    )
    assert profile.cabinet_payload["notifications"][0]["is_read"] == 1
    assert profile.dashboard_snapshot["unread"] == 0

    review, _ = await service.apply_action(
        7,
        "business_reviews",
        "reply",
        record_id=8,
        data={"reply": "Rahmat"},
    )
    assert review is not None
    assert review["business_reply"] == "Rahmat"


@pytest.mark.asyncio
async def test_readonly_resources_cannot_be_created_or_deleted():
    service = BusinessOnlineService(FakeDatabase(business_profile()).session)

    with pytest.raises(ApiError) as create_error:
        await service.create_record(7, "followers", {"name": "Soxta"})
    assert create_error.value.code == "business_online_operation_forbidden"

    with pytest.raises(ApiError) as delete_error:
        await service.delete_record(7, "business_subscriptions", 1)
    assert delete_error.value.code == "business_online_operation_forbidden"


@pytest.mark.asyncio
async def test_unknown_resource_is_not_exposed():
    service = BusinessOnlineService(FakeDatabase(business_profile()).session)

    with pytest.raises(ApiError) as error:
        await service.read_resource(7, "staff")

    assert error.value.code == "business_online_resource_not_found"
