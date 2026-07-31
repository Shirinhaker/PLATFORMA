from contextlib import asynccontextmanager

import pytest

from app.business_online.service import BusinessOnlineService
from app.core.errors import ApiError
from app.profiles.model import BusinessProfile, UserProfile


class FakeSession:
    def __init__(
        self,
        profile: BusinessProfile,
        users: dict[int, UserProfile] | None = None,
    ):
        self.profile = profile
        self.users = users or {}
        self.commits = 0

    async def scalar(self, statement):
        return self.profile

    async def get(self, model, account_id):
        if model is BusinessProfile and account_id == self.profile.account_id:
            return self.profile
        if model is UserProfile:
            return self.users.get(account_id)
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None


class FakeDatabase:
    def __init__(
        self,
        profile: BusinessProfile,
        users: dict[int, UserProfile] | None = None,
    ):
        self.session_value = FakeSession(profile, users)

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


def user_profile(account_id: int, name: str) -> UserProfile:
    return UserProfile(
        account_id=account_id,
        name=name,
        phone="",
        public_username=f"user{account_id}",
        region="",
        district="",
        mahalla="",
        latitude=None,
        longitude=None,
        location_exact=False,
        avatar_object_key="",
        avatar_x=50,
        avatar_y=50,
        avatar_zoom=1,
        followers_count=0,
        following_count=0,
        has_business=False,
        dashboard_snapshot={},
        recent_activity=[],
        specialist_profile={},
        cabinet_payload={"notifications": []},
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


@pytest.mark.asyncio
async def test_medical_provider_create_update_and_safe_setup_match_v1656():
    profile = business_profile()
    profile.direction = "Tibbiy xizmatlar"
    profile.cabinet_payload.update({
        "staff": [
            {
                "id": 11,
                "name": "Ali Valiyev",
                "profession": "Terapevt",
                "status": "active",
                "password_hash": "sir",
            },
            {
                "id": 12,
                "name": "Nofaol",
                "profession": "Hamshira",
                "status": "inactive",
            },
        ],
        "items": [
            {
                "id": 31,
                "name": "Qabul",
                "kind": "service",
                "queue_enabled": 1,
            },
            {
                "id": 32,
                "name": "Navbatsiz",
                "kind": "service",
                "queue_enabled": 0,
            },
        ],
        "medical_doctors": [],
        "medical_doctor_services": [],
        "medical_queue": [],
        "medical_queue_history": [],
    })
    service = BusinessOnlineService(FakeDatabase(profile).session)

    assert await service.read_resource(7, "medical_staff") == [{
        "id": 11,
        "name": "Ali Valiyev",
        "profession": "Terapevt",
        "status": "active",
    }]

    doctor, rows = await service.create_record(
        7,
        "medical_doctors",
        {
            "staff_id": 11,
            "specialty": "Kardiolog",
            "experience_years": 8,
            "qualification": "Oliy toifa",
            "work_days": "1,2,3,4,5,6",
            "work_start": "08:00",
            "work_end": "17:00",
            "avg_minutes": 20,
            "room": "12-xona",
            "bio": "Tajribali",
            "status": "active",
            "mode": "slot",
            "item_ids": [31],
        },
    )

    assert doctor["id"] == 1
    assert doctor["staff_id"] == 11
    assert doctor["item_ids"] == [31]
    assert doctor["name"] == "Ali Valiyev"
    assert rows == [doctor]
    assert profile.cabinet_payload["medical_doctor_services"] == [{
        "business_id": 7,
        "staff_id": 11,
        "item_id": 31,
        "active": 1,
        "duration_minutes": 20,
    }]

    updated, rows = await service.patch_record(
        7,
        "medical_doctors",
        1,
        {
            "staff_id": 999,
            "room": "15-xona",
            "avg_minutes": 30,
            "item_ids": [31],
        },
    )
    assert updated["staff_id"] == 11
    assert updated["room"] == "15-xona"
    assert updated["avg_minutes"] == 30
    assert rows[0]["item_ids"] == [31]
    assert profile.cabinet_payload["medical_doctor_services"][0][
        "duration_minutes"
    ] == 30

    with pytest.raises(ApiError) as invalid_item:
        await service.patch_record(
            7,
            "medical_doctors",
            1,
            {"item_ids": [32]},
        )
    assert invalid_item.value.message == "Navbat yoqilgan xizmatni tanlang."


@pytest.mark.asyncio
async def test_medical_lists_keep_the_v1656_database_order():
    profile = business_profile()
    profile.direction = "Tibbiy xizmatlar"
    profile.cabinet_payload.update({
        "staff": [
            {"id": 12, "name": "Zafar", "status": "active"},
            {"id": 11, "name": "Ali", "status": "active"},
        ],
        "items": [
            {"id": 32, "name": "UZI", "kind": "service", "queue_enabled": 1},
            {"id": 31, "name": "Qabul", "kind": "service", "queue_enabled": 1},
        ],
        "medical_doctors": [
            {"id": 2, "staff_id": 12, "status": "inactive"},
            {"id": 1, "staff_id": 11, "status": "active"},
        ],
        "medical_doctor_services": [],
        "medical_queue": [
            {
                "id": 43,
                "staff_id": 12,
                "item_id": 32,
                "queue_no": 1,
                "queue_date": "2026-08-01",
            },
            {
                "id": 42,
                "staff_id": 11,
                "item_id": 31,
                "queue_no": 2,
                "queue_date": "2026-08-01",
            },
            {
                "id": 41,
                "staff_id": 11,
                "item_id": 31,
                "queue_no": 1,
                "queue_date": "2026-08-01",
            },
        ],
    })
    service = BusinessOnlineService(FakeDatabase(profile).session)

    staff = await service.read_resource(7, "medical_staff")
    doctors = await service.read_resource(7, "medical_doctors")
    queue = await service.read_resource(7, "medical_queue")

    assert [row["id"] for row in staff] == [11, 12]
    assert [row["id"] for row in doctors] == [1, 2]
    assert [row["id"] for row in queue] == [41, 42, 43]


@pytest.mark.asyncio
async def test_medical_direction_guard_matches_all_fourteen_v1656_directions():
    profile = business_profile()
    service = BusinessOnlineService(FakeDatabase(profile).session)

    with pytest.raises(ApiError) as forbidden:
        await service.read_resource(7, "medical_queue")
    assert forbidden.value.status_code == 403
    assert forbidden.value.message == "Bu yo'nalishda navbat tizimi ishlamaydi."

    for direction in (
        "Transport va logistika",
        "Xizmat ko'rsatish",
        "Maishiy xizmatlar",
        "Qurilish",
        "Tibbiy xizmatlar",
        "Ko'chmas mulk",
        "Axborot texnologiyalari",
        "Konsalting va professional",
        "Madaniyat, sport, ko'ngilochar",
        "Turizm va mehmonxona",
        "Reklama va marketing",
        "Poligrafiya va nashriyot",
        "Moliyaviy faoliyat",
        "Import-eksport",
    ):
        profile.direction = direction
        assert await service.read_resource(7, "medical_queue") == []


@pytest.mark.asyncio
async def test_medical_offline_status_notifications_and_swap_match_v1656():
    profile = business_profile()
    profile.direction = "Tibbiy xizmatlar"
    profile.cabinet_payload.update({
        "staff": [{
            "id": 11,
            "name": "Ali Valiyev",
            "profession": "Terapevt",
            "status": "active",
        }],
        "items": [{
            "id": 31,
            "name": "Qabul",
            "kind": "service",
            "queue_enabled": 1,
        }],
        "medical_doctors": [{
            "id": 5,
            "staff_id": 11,
            "status": "active",
            "mode": "live",
            "work_days": "1,2,3,4,5,6",
            "work_start": "08:00",
            "work_end": "17:00",
            "avg_minutes": 20,
        }],
        "medical_doctor_services": [{
            "business_id": 7,
            "staff_id": 11,
            "item_id": 31,
            "active": 1,
            "duration_minutes": 20,
        }],
        "medical_queue": [
            {
                "id": 41,
                "item_id": 31,
                "staff_id": 11,
                "user_id": 70,
                "patient_name": "Vali",
                "queue_date": "2026-08-01",
                "queue_no": 1,
                "queue_code": "QAB-001",
                "source": "online",
                "status": "waiting",
                "slot_time": "",
            },
            {
                "id": 42,
                "item_id": 31,
                "staff_id": 11,
                "user_id": 71,
                "patient_name": "Hasan",
                "queue_date": "2026-08-01",
                "queue_no": 2,
                "queue_code": "QAB-002",
                "source": "online",
                "status": "waiting",
                "slot_time": "",
            },
        ],
        "medical_queue_history": [],
    })
    users = {
        70: user_profile(70, "Vali"),
        71: user_profile(71, "Hasan"),
    }
    service = BusinessOnlineService(FakeDatabase(profile, users).session)

    offline, rows = await service.apply_action(
        7,
        "medical_queue",
        "offline_add",
        record_id=None,
        data={
            "item_id": 31,
            "staff_id": 11,
            "patient_name": "Olim",
            "phone": "901234567",
            "queue_date": "2026-08-01",
        },
    )
    assert offline is not None
    assert offline["queue_no"] == 3
    assert offline["queue_code"] == "QAB-003"
    assert offline["source"] == "offline"
    assert rows[-1]["service_name"] == "Qabul"
    assert rows[-1]["doctor_name"] == "Ali Valiyev"

    called, _ = await service.apply_action(
        7,
        "medical_queue",
        "set_status",
        record_id=41,
        data={"status": "called"},
    )
    assert called is not None
    assert called["status"] == "called"
    assert profile.cabinet_payload["medical_queue_history"][-1]["action"] == "status"
    first_notification = users[70].cabinet_payload["notifications"][0]
    assert {
        key: first_notification[key]
        for key in (
            "title",
            "body",
            "medical_queue_id",
            "action_type",
            "is_read",
        )
    } == {
        "title": "Navbatingiz keldi",
        "body": "QAB-001 navbat shifokor tomonidan chaqirildi.",
        "medical_queue_id": 41,
        "action_type": "medical_queue_called",
        "is_read": 0,
    }
    assert users[71].cabinet_payload["notifications"][0]["title"] == (
        "Navbatingiz yaqinlashdi"
    )

    await service.apply_action(
        7,
        "medical_queue",
        "set_status",
        record_id=41,
        data={"status": "cancelled"},
    )
    assert users[70].cabinet_payload["notifications"][-1]["body"] == (
        "QAB-001 navbat muassasa tomonidan bekor qilindi."
    )

    swapped, rows = await service.apply_action(
        7,
        "medical_queue",
        "swap",
        record_id=41,
        data={"other_queue_id": 42},
    )
    assert swapped is not None
    assert swapped["queue_no"] == 2
    assert swapped["queue_code"] == "QAB-002"
    second = next(row for row in rows if row["id"] == 42)
    assert second["queue_no"] == 1
    assert second["queue_code"] == "QAB-001"
    assert users[70].cabinet_payload["notifications"][-1]["title"] == (
        "Navbat raqami o‘zgardi"
    )
    assert users[71].cabinet_payload["notifications"][-1]["body"] == (
        "Yangi navbat raqamingiz: QAB-001."
    )


@pytest.mark.asyncio
async def test_education_enrollments_are_guarded_enriched_and_sorted_like_v1656():
    profile = business_profile()
    profile.cabinet_payload.update({
        "items": [
            {"id": 51, "name": "Ingliz tili"},
            {"id": 52, "name": "Matematika"},
        ],
        "education_groups": [
            {"id": 61, "name": "English A1", "course_item_id": 51, "status": "active"},
            {"id": 62, "name": "O'chirilgan", "course_item_id": 51, "status": "deleted"},
        ],
        "education_students": [],
        "education_enrollments": [
            {"id": 72, "course_item_id": 52, "status": "accepted", "group_id": None},
            {"id": 71, "course_item_id": 51, "status": "new", "group_id": 61},
            {"id": 73, "course_item_id": 51, "status": "new", "group_id": None},
        ],
    })
    service = BusinessOnlineService(FakeDatabase(profile).session)

    with pytest.raises(ApiError) as forbidden:
        await service.read_resource(7, "education_enrollments")
    assert forbidden.value.status_code == 403
    assert forbidden.value.message == (
        "Bu bo'lim faqat Ta'lim faoliyati yo'nalishi uchun."
    )

    profile.direction = "Ta'lim faoliyati"
    groups = await service.read_resource(7, "education_groups")
    enrollments = await service.read_resource(7, "education_enrollments")

    assert [row["id"] for row in groups] == [61]
    assert [row["id"] for row in enrollments] == [73, 71, 72]
    assert enrollments[1]["course_name"] == "Ingliz tili"
    assert enrollments[1]["group_name"] == "English A1"
    assert enrollments[2]["course_name"] == "Matematika"


@pytest.mark.asyncio
async def test_education_enrollment_accept_and_reject_match_v1656_student_flow():
    profile = business_profile()
    profile.direction = "Ta'lim faoliyati"
    profile.cabinet_payload.update({
        "items": [{"id": 51, "name": "Ingliz tili"}],
        "education_groups": [
            {"id": 61, "name": "English A1", "course_item_id": 51, "status": "active"},
            {"id": 62, "name": "Boshqa kurs", "course_item_id": 52, "status": "active"},
        ],
        "education_students": [],
        "education_enrollments": [
            {
                "id": 71,
                "course_item_id": 51,
                "user_id": 70,
                "customer_name": "Ali Valiyev",
                "phone": "+998901234567",
                "note": "Kechki guruh",
                "status": "new",
            },
            {
                "id": 72,
                "course_item_id": 51,
                "user_id": 71,
                "customer_name": "Vali",
                "phone": "+998909876543",
                "note": "",
                "status": "new",
            },
        ],
    })
    service = BusinessOnlineService(FakeDatabase(profile).session)

    with pytest.raises(ApiError) as mismatch:
        await service.apply_action(
            7,
            "education_enrollments",
            "accept",
            record_id=71,
            data={"group_id": 62},
        )
    assert mismatch.value.message == "Tanlangan guruh boshqa kursga tegishli."

    accepted, rows = await service.apply_action(
        7,
        "education_enrollments",
        "accept",
        record_id=71,
        data={"group_id": 61},
    )
    assert accepted is not None
    assert accepted["status"] == "accepted"
    assert accepted["group_name"] == "English A1"
    student = profile.cabinet_payload["education_students"][0]
    assert student["user_id"] == 70
    assert student["full_name"] == "Ali Valiyev"
    assert student["phone"] == "+998901234567"
    assert student["group_id"] == 61
    assert student["joined_date"]
    assert student["note"] == "Kurs arizasi: Kechki guruh"
    assert student["monthly_fee"] == 0
    assert student["status"] == "active"
    assert rows[0]["id"] == 72

    rejected, _ = await service.apply_action(
        7,
        "education_enrollments",
        "reject",
        record_id=72,
        data={},
    )
    assert rejected is not None
    assert rejected["status"] == "rejected"

    with pytest.raises(ApiError) as not_new:
        await service.apply_action(
            7,
            "education_enrollments",
            "reject",
            record_id=72,
            data={},
        )
    assert not_new.value.status_code == 404
    assert not_new.value.message == "Yangi ariza topilmadi."
