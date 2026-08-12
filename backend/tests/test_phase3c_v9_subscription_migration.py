from types import SimpleNamespace
import sqlite3

import pytest

from app.legacy_migration.business_subscription_stage import (
    import_business_subscriptions,
)
from app.legacy_migration.demo_prune import prune_demo_records
from app.legacy_migration.model import LegacyIdMap
from app.legacy_migration.profile_parity_v7 import enrich_business_cabinets
from app.legacy_migration.real_source_v9 import copy_real_source
from app.payments.model import BusinessSubscription


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self):
        self.added = []

    async def scalars(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        assert entity is LegacyIdMap
        return ScalarResult(SimpleNamespace(target_id=17))

    async def scalar(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        assert entity is BusinessSubscription
        legacy_id = int(statement.compile().params["legacy_source_id_1"])
        return next(
            (
                row
                for row in self.added
                if isinstance(row, BusinessSubscription)
                and row.legacy_source_id == legacy_id
            ),
            None,
        )

    def add(self, row):
        row.id = len(self.added) + 1
        self.added.append(row)

    async def flush(self):
        return None


def legacy_source() -> sqlite3.Connection:
    source = sqlite3.connect(":memory:")
    source.row_factory = sqlite3.Row
    source.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            login TEXT NOT NULL,
            tg_id INTEGER
        );
        CREATE TABLE businesses (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL
        );
        CREATE TABLE listings (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            business_id INTEGER
        );
        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            business_id INTEGER
        );
        CREATE TABLE business_subscriptions (
            id INTEGER PRIMARY KEY,
            business_id INTEGER NOT NULL,
            plan_code TEXT NOT NULL,
            duration_months INTEGER NOT NULL,
            starts_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            status TEXT NOT NULL,
            is_demo INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            payment_request_id INTEGER
        );
        CREATE TABLE advertisements (
            id INTEGER PRIMARY KEY,
            business_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            is_demo INTEGER NOT NULL
        );

        INSERT INTO users VALUES
            (5, 'real_owner', 1423181561),
            (6, 'demo_v1616_qumqorgon_01', NULL);
        INSERT INTO businesses VALUES
            (7, 5, 'Haqiqiy biznes'),
            (8, 6, 'Demo biznes');
        INSERT INTO business_subscriptions VALUES (
            11, 7, 'plus', 3, 1722211200, 1893456000,
            'active', 1, 1722211200, NULL
        ), (
            12, 8, 'pro', 12, 1722211200, 1893456000,
            'active', 1, 1722211200, NULL
        );
        INSERT INTO advertisements VALUES (21, 7, 'Demo reklama', 1);
        """
    )
    return source


def pruned_copy() -> sqlite3.Connection:
    source = legacy_source()
    try:
        removed = prune_demo_records(source)
        assert removed["users"] == 1
        assert removed["businesses"] == 1
        assert removed["business_subscriptions"] == 1
        return copy_real_source(source)
    finally:
        source.close()


def test_v9_real_source_preserves_real_business_demo_activated_subscription():
    copied = pruned_copy()
    try:
        subscription = copied.execute(
            "SELECT * FROM business_subscriptions"
        ).fetchone()
        assert subscription is not None
        assert subscription["business_id"] == 7
        assert subscription["plan_code"] == "plus"
        assert subscription["is_demo"] == 1
        assert copied.execute("SELECT * FROM advertisements").fetchall() == []
    finally:
        copied.close()


@pytest.mark.asyncio
async def test_real_demo_activated_subscription_remains_in_cabinet_payload(
    monkeypatch,
):
    copied = pruned_copy()

    profile = SimpleNamespace(cabinet_payload={})

    async def mapping(*_args):
        return SimpleNamespace(target_id=17)

    class CabinetSession:
        async def get(self, *_args):
            return profile

    monkeypatch.setattr(
        "app.legacy_migration.profile_parity_v7._find_mapping",
        mapping,
    )
    try:
        await enrich_business_cabinets(CabinetSession(), copied)
    finally:
        copied.close()

    assert profile.cabinet_payload["business_subscriptions"] == [
        {
            "id": 11,
            "business_id": 7,
            "plan_code": "plus",
            "duration_months": 3,
            "starts_at": 1722211200,
            "expires_at": 1893456000,
            "status": "active",
            "is_demo": 1,
            "created_at": 1722211200,
            "payment_request_id": None,
        }
    ]


@pytest.mark.asyncio
async def test_typed_subscription_import_is_relational_and_idempotent():
    copied = pruned_copy()
    session = FakeSession()
    run = SimpleNamespace(id=9)
    try:
        first = await import_business_subscriptions(session, copied, run)
        second = await import_business_subscriptions(session, copied, run)
    finally:
        copied.close()

    assert first.created == 1
    assert second.reused == 1
    assert len(session.added) == 1
    subscription = session.added[0]
    assert subscription.business_account_id == 17
    assert subscription.legacy_source_id == 11
    assert subscription.plan_code == "plus"
    assert subscription.status == "active"
    assert subscription.is_demo is True
