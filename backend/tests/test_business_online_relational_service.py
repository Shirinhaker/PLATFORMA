from __future__ import annotations

from contextlib import asynccontextmanager
from copy import deepcopy

import pytest

from app.business_online.service_relational import BusinessOnlineService
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


class FakeCabinetRecordRepository:
    def __init__(self):
        self.payload: dict[tuple[int, str], dict[str, list[dict]]] = {}
        self.replacements: list[str] = []

    async def has_resource(self, session, *, account_id, account_type, resource):
        return resource in self.payload.get((account_id, account_type), {})

    async def read_resource(self, session, *, account_id, account_type, resource):
        return deepcopy(
            self.payload.get((account_id, account_type), {}).get(resource, [])
        )

    async def read_payload(self, session, *, account_id, account_type):
        return deepcopy(self.payload.get((account_id, account_type), {}))

    async def replace_resource(
        self,
        session,
        *,
        account_id,
        account_type,
        resource,
        rows,
    ):
        self.payload.setdefault((account_id, account_type), {})[resource] = deepcopy(rows)
        self.replacements.append(resource)


class FakeCatalogSync:
    def __init__(self):
        self.calls = []

    async def __call__(
        self,
        session,
        *,
        account_id,
        owner_name,
        payload,
        changed_resources,
    ):
        self.calls.append({
            "account_id": account_id,
            "owner_name": owner_name,
            "payload": deepcopy(payload),
            "changed_resources": set(changed_resources),
        })


def profile() -> BusinessProfile:
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
        dashboard_snapshot={"new_orders": 1},
        recent_activity=[],
        cabinet_payload={
            "items": [{"id": 4, "name": "Eski mahsulot", "price": 10000}],
            "orders": [{
                "id": 44,
                "title": "Muhr",
                "status": "new",
                "order_type": "product",
                "created_at": 100,
            }],
            "notifications": [{"id": 7, "title": "Yangi", "is_read": 0}],
            "business_subscriptions": [],
            "subscription_payments": [],
            "followers": [{"id": 9, "name": "Vali"}],
            "following": [{"id": 10, "name": "Hamkor"}],
            "business_reviews": [{"id": 8, "rating": 5}],
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
async def test_create_uses_relational_primary_store_and_syncs_json_fallback():
    business = profile()
    original_orders = deepcopy(business.cabinet_payload["orders"])
    database = FakeDatabase(business)
    repository = FakeCabinetRecordRepository()
    catalog_sync = FakeCatalogSync()
    service = BusinessOnlineService(
        database.session,
        repository,
        catalog_sync=catalog_sync,
    )

    item, rows = await service.create_record(
        7,
        "items",
        {"name": "Yangi mahsulot", "price": 20000},
    )

    assert item["id"] == 5
    assert [row["name"] for row in rows] == ["Eski mahsulot", "Yangi mahsulot"]
    assert business.cabinet_payload["items"] == rows
    assert business.cabinet_payload["orders"] == original_orders
    assert repository.replacements == ["items"]
    assert await service.read_resource(7, "items") == rows
    assert database.session_value.commits == 1
    assert len(catalog_sync.calls) == 1
    assert catalog_sync.calls[0]["account_id"] == 7
    assert catalog_sync.calls[0]["owner_name"] == "Muhr"
    assert catalog_sync.calls[0]["changed_resources"] == {"items"}
    assert catalog_sync.calls[0]["payload"]["items"] == rows


@pytest.mark.asyncio
async def test_action_persists_every_changed_resource_in_both_stores():
    business = profile()
    database = FakeDatabase(business)
    repository = FakeCabinetRecordRepository()
    service = BusinessOnlineService(database.session, repository)

    subscription, rows = await service.apply_action(
        7,
        "business_subscriptions",
        "request_plan",
        record_id=None,
        data={"plan": "plus", "duration_months": 3, "amount": 149000},
    )

    assert subscription is not None
    assert subscription["plan"] == "plus"
    assert rows[0]["status"] == "pending_payment"
    assert set(repository.replacements) == {
        "business_subscriptions",
        "subscription_payments",
    }
    payments = await service.read_resource(7, "subscription_payments")
    assert payments[0]["amount_snapshot"] == 149000
    assert business.cabinet_payload["business_subscriptions"] == rows
    assert business.cabinet_payload["subscription_payments"] == payments


@pytest.mark.asyncio
async def test_relational_action_updates_derived_counts_and_json_fallback():
    business = profile()
    database = FakeDatabase(business)
    repository = FakeCabinetRecordRepository()
    service = BusinessOnlineService(database.session, repository)

    await service.apply_action(
        7,
        "notifications",
        "mark_all_read",
        record_id=None,
        data={},
    )

    notifications = await service.read_resource(7, "notifications")
    assert notifications[0]["is_read"] == 1
    assert business.dashboard_snapshot["unread"] == 0
    assert business.cabinet_payload["notifications"] == notifications


@pytest.mark.asyncio
async def test_dining_action_and_delete_persist_all_relational_resources():
    business = profile()
    business.direction = "Umumiy ovqatlanish"
    business.cabinet_payload.update({
        "items": [{
            "id": 21,
            "name": "Tuxum barak",
            "price": 20000,
            "unit": "dona",
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
    database = FakeDatabase(business)
    repository = FakeCabinetRecordRepository()
    service = BusinessOnlineService(database.session, repository)

    place, places = await service.apply_action(
        7,
        "dining_places",
        "create_order",
        record_id=5,
        data={"items": [{"item_id": 21, "qty": 1}]},
    )

    assert place is not None
    assert place["active_kind"] == "order"
    assert places[0]["total"] == 20000
    assert set(repository.replacements) == {
        "dining_places",
        "dining_orders",
        "notifications",
    }
    assert business.cabinet_payload["dining_places"] == places
    assert business.cabinet_payload["dining_orders"][0]["total"] == 20000
    assert business.cabinet_payload["dining_orders"][0]["waiter_name"] == "Muhr"
    assert len(business.cabinet_payload["notifications"]) == 2

    repository.replacements.clear()
    assert await service.delete_record(7, "dining_places", 5) == []
    assert set(repository.replacements) == {"dining_places", "dining_orders"}
    assert business.cabinet_payload["dining_orders"] == []


@pytest.mark.asyncio
async def test_medical_relational_flow_persists_links_history_and_user_notification():
    business = profile()
    business.direction = "Tibbiy xizmatlar"
    business.cabinet_payload.update({
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
        "medical_doctors": [],
        "medical_doctor_services": [],
        "medical_queue": [{
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
        }],
        "medical_queue_history": [],
    })
    user = user_profile(70, "Vali")
    database = FakeDatabase(business, {70: user})
    repository = FakeCabinetRecordRepository()
    service = BusinessOnlineService(database.session, repository)

    doctor, _ = await service.create_record(
        7,
        "medical_doctors",
        {
            "staff_id": 11,
            "item_ids": [31],
            "specialty": "Kardiolog",
            "avg_minutes": 20,
        },
    )
    assert doctor["item_ids"] == [31]
    assert set(repository.replacements) == {
        "medical_doctors",
        "medical_doctor_services",
    }
    assert business.cabinet_payload["medical_doctor_services"][0]["item_id"] == 31

    repository.replacements.clear()
    called, _ = await service.apply_action(
        7,
        "medical_queue",
        "set_status",
        record_id=41,
        data={"status": "called"},
    )
    assert called is not None
    assert called["status"] == "called"
    assert set(repository.replacements) == {
        "medical_queue",
        "medical_queue_history",
        "notifications",
    }
    assert repository.payload[(70, "user")]["notifications"][0][
        "action_type"
    ] == "medical_queue_called"
    assert user.cabinet_payload["notifications"][0]["medical_queue_id"] == 41


@pytest.mark.asyncio
async def test_education_accept_persists_enrollment_and_student_in_both_stores():
    business = profile()
    business.direction = "Ta'lim faoliyati"
    business.cabinet_payload.update({
        "items": [{"id": 51, "name": "Ingliz tili"}],
        "education_groups": [
            {"id": 61, "name": "English A1", "course_item_id": 51, "status": "active"},
        ],
        "education_students": [],
        "education_enrollments": [{
            "id": 71,
            "course_item_id": 51,
            "user_id": 70,
            "customer_name": "Ali Valiyev",
            "phone": "+998901234567",
            "note": "Kechki guruh",
            "status": "new",
        }],
    })
    database = FakeDatabase(business)
    repository = FakeCabinetRecordRepository()
    service = BusinessOnlineService(database.session, repository)

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
    assert set(repository.replacements) == {
        "education_enrollments",
        "education_students",
    }
    stored_enrollment = repository.payload[(7, "business")][
        "education_enrollments"
    ][0]
    assert stored_enrollment["id"] == rows[0]["id"]
    assert stored_enrollment["status"] == "accepted"
    assert stored_enrollment["group_id"] == 61
    student = repository.payload[(7, "business")]["education_students"][0]
    assert student["full_name"] == "Ali Valiyev"
    assert student["group_id"] == 61
    assert business.cabinet_payload["education_students"] == [student]
