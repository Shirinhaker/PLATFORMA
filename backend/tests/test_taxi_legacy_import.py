import sqlite3
from types import SimpleNamespace

import pytest

from app.legacy_migration.model import LegacyIdMap
from app.orders.model import Order
from app.taxi.legacy_import import import_taxi_domain
from app.taxi.model import TaxiDriver, TaxiRide


class One:
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
        return One(SimpleNamespace(target_id=17))

    async def scalar(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity is Order:
            return None
        candidates = [row for row in self.added if isinstance(row, entity)]
        return candidates[0] if candidates else None

    def add(self, row):
        row.id = len(self.added) + 1
        self.added.append(row)

    async def flush(self):
        return None


def source_database():
    source = sqlite3.connect(":memory:")
    source.executescript(
        """
        CREATE TABLE drivers(
          id INTEGER PRIMARY KEY, user_id INTEGER, phone TEXT, car_model TEXT,
          car_color TEXT, car_plate TEXT, service TEXT, available INTEGER,
          rating_sum INTEGER, rating_cnt INTEGER, balance INTEGER,
          status TEXT, created_at INTEGER
        );
        CREATE TABLE rides(
          id INTEGER PRIMARY KEY, customer_id INTEGER, kind TEXT,
          from_addr TEXT, to_addr TEXT, from_lat REAL, from_lng REAL,
          to_lat REAL, to_lng REAL, dist_km REAL, dur_min INTEGER,
          meter_km REAL, ozim INTEGER, cargo TEXT, car_type TEXT, note TEXT,
          status TEXT, driver_id INTEGER, src_order_id INTEGER,
          created_at INTEGER, accepted_at INTEGER
        );
        INSERT INTO drivers VALUES(
          3, 5, '+99890', 'Cobalt', 'oq', '01 A 123 BC', 'both', 1,
          8, 2, 5000, 'active', 1723283200
        );
        INSERT INTO rides VALUES(
          9, 5, 'taxi', 'A', 'B', 41.3, 69.2, 41.31, 69.21,
          3.6, 8, NULL, 0, '', '', '', 'accepted', 3, NULL,
          1723283300, 1723283400
        );
        """
    )
    return source


@pytest.mark.asyncio
async def test_legacy_taxi_import_is_relational_and_idempotent():
    source = source_database()
    session = FakeSession()
    run = SimpleNamespace(id=4)
    try:
        first = await import_taxi_domain(session, source, run)
        second = await import_taxi_domain(session, source, run)
    finally:
        source.close()

    assert first.created == 2
    assert second.reused == 2
    assert len(session.added) == 2
    driver = next(row for row in session.added if isinstance(row, TaxiDriver))
    ride = next(row for row in session.added if isinstance(row, TaxiRide))
    assert driver.user_account_id == 17
    assert ride.customer_account_id == 17
    assert ride.driver_id == driver.id
    assert ride.accepted_at.tzinfo is not None
