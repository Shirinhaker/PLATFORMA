from __future__ import annotations

from contextlib import asynccontextmanager
from copy import deepcopy

import pytest

from app.business_online.service_relational import BusinessOnlineService
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


@pytest.mark.asyncio
async def test_create_uses_relational_primary_store_without_mutating_profile_json():
    business = profile()
    original_json = deepcopy(business.cabinet_payload)
    database = FakeDatabase(business)
    repository = FakeCabinetRecordRepository()
    service = BusinessOnlineService(database.session, repository)

    item, rows = await service.create_record(
        7,
        "items",
        {"name": "Yangi mahsulot", "price": 20000},
    )

    assert item["id"] == 5
    assert [row["name"] for row in rows] == ["Eski mahsulot", "Yangi mahsulot"]
    assert business.cabinet_payload == original_json
    assert repository.replacements == ["items"]
    assert await service.read_resource(7, "items") == rows
    assert database.session_value.commits == 1


@pytest.mark.asyncio
async def test_action_persists_every_changed_related_resource():
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
    assert business.cabinet_payload["business_subscriptions"] == []


@pytest.mark.asyncio
async def test_relational_action_updates_derived_counts_without_json_write():
    business = profile()
    original_json = deepcopy(business.cabinet_payload)
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
    assert business.cabinet_payload == original_json
