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


@pytest.mark.asyncio
async def test_dining_flow_matches_v1656_place_booking_and_order_contract():
    profile = business_profile()
    profile.direction = "Umumiy ovqatlanish"
    profile.cabinet_payload.update({
        "items": [{
            "id": 21,
            "name": "Tuxum barak",
            "price": 20000,
            "unit": "dona",
            "stock_type": "ready_food",
        }],
        "dining_places": [],
        "dining_orders": [],
        "notifications": [],
    })
    service = BusinessOnlineService(FakeDatabase(profile).session)

    place, places = await service.create_record(
        7,
        "dining_places",
        {"kind": "table", "name": "Stol 1", "seats": 4},
    )
    assert {
        key: place[key]
        for key in ("id", "kind", "name", "seats", "x", "y", "locked")
    } == {
        "id": 1,
        "kind": "table",
        "name": "Stol 1",
        "seats": 4,
        "x": 4,
        "y": 4,
        "locked": 1,
    }
    assert places == [place]

    booked, places = await service.apply_action(
        7,
        "dining_places",
        "book",
        record_id=1,
        data={
            "customer_name": "Ali",
            "phone": "901234567",
            "booking_date": "2026-08-01",
            "booking_time": "19:30",
            "guests": 3,
            "note": "",
        },
    )
    assert booked is not None
    assert booked["active_kind"] == "booking"
    assert places[0]["customer_name"] == "Ali"

    ordered, places = await service.apply_action(
        7,
        "dining_places",
        "create_order",
        record_id=1,
        data={
            "items": [{"item_id": 21, "qty": 2}],
            "customer_name": "Vali",
            "note": "Issiq",
        },
    )
    assert ordered is not None
    assert ordered["active_kind"] == "order"
    assert ordered["total"] == 40000
    order_id = ordered["active_id"]
    orders = profile.cabinet_payload["dining_orders"]
    assert orders[1]["id"] == order_id
    assert orders[1]["waiter_name"] == "Muhr"
    assert orders[1]["items"] == [{
        "item_id": 21,
        "name": "Tuxum barak",
        "qty": 2.0,
        "unit": "dona",
        "price": 20000,
        "total": 40000,
    }]
    assert places[0]["active_id"] == order_id

    updated_order, _ = await service.apply_action(
        7,
        "dining_orders",
        "add_items",
        record_id=order_id,
        data={"items": [{"item_id": 21, "qty": 1}], "note": ""},
    )
    assert updated_order is not None
    assert updated_order["total"] == 60000
    assert updated_order["kitchen_status"] == "preparing"
    assert [row["title"] for row in profile.cabinet_payload["notifications"]] == [
        "Yangi ichki zakaz",
        "Yangi ochiq hisob",
        "Ichki zakazga yangi taom qo'shildi",
        "Ichki zakaz hisobi yangilandi",
    ]
    assert profile.dashboard_snapshot["occupied_places"] == 1


@pytest.mark.asyncio
async def test_dining_price_snapshot_matches_v1656_twelve_digit_cap():
    profile = business_profile()
    profile.direction = "Umumiy ovqatlanish"
    profile.cabinet_payload.update({
        "items": [{
            "id": 21,
            "name": "Etalon narx",
            "price": "1 234 567 890 123 so'm",
            "stock_type": "ready_food",
        }],
        "dining_places": [{
            "id": 5,
            "kind": "table",
            "name": "Stol 1",
            "seats": 4,
            "x": 4,
            "y": 4,
            "locked": 1,
        }],
        "dining_orders": [],
        "notifications": [],
    })
    service = BusinessOnlineService(FakeDatabase(profile).session)

    ordered, _ = await service.apply_action(
        7,
        "dining_places",
        "create_order",
        record_id=5,
        data={"items": [{"item_id": 21, "qty": 1}]},
    )

    assert ordered is not None
    assert ordered["total"] == 123456789012
    assert profile.cabinet_payload["dining_orders"][0]["waiter_name"] == "Muhr"


@pytest.mark.asyncio
async def test_dining_direction_clear_guard_and_delete_cascade_match_v1656():
    profile = business_profile()
    service = BusinessOnlineService(FakeDatabase(profile).session)

    with pytest.raises(ApiError) as forbidden:
        await service.read_resource(7, "dining_places")
    assert forbidden.value.status_code == 403
    assert forbidden.value.message == (
        "Bu bo'lim faqat Umumiy ovqatlanish yo'nalishi uchun."
    )

    profile.direction = "Umumiy ovqatlanish"
    profile.cabinet_payload.update({
        "dining_places": [{
            "id": 5,
            "kind": "table",
            "name": "Stol 1",
            "seats": 4,
            "x": 4,
            "y": 4,
            "locked": 1,
        }],
        "dining_orders": [{
            "id": 41,
            "place_id": 5,
            "kind": "order",
            "status": "active",
            "kitchen_status": "preparing",
            "payment_status": "open",
            "total": 20000,
            "items": [],
        }],
    })

    with pytest.raises(ApiError) as unfinished:
        await service.apply_action(
            7,
            "dining_places",
            "clear",
            record_id=5,
            data={},
        )
    assert unfinished.value.status_code == 409
    assert unfinished.value.message == (
        "Stolni bo'shatish uchun taom tayyor va to'lov tasdiqlangan "
        "bo'lishi kerak."
    )

    profile.cabinet_payload["dining_orders"][0].update({
        "kitchen_status": "done",
        "payment_status": "confirmed",
    })
    cleared, _ = await service.apply_action(
        7,
        "dining_places",
        "clear",
        record_id=5,
        data={},
    )
    assert cleared is not None
    assert cleared.get("active_id") is None
    assert profile.cabinet_payload["dining_orders"][0]["status"] == "done"

    assert await service.delete_record(7, "dining_places", 5) == []
    assert profile.cabinet_payload["dining_orders"] == []
