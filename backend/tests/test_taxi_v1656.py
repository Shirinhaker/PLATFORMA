from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.core.errors import ApiError
from app.db.base import Base
from app.profiles.model import UserProfile
from app.taxi.model import TaxiDriver, TaxiRide
from app.taxi.schemas import DriverWrite, RideCreate
from app.taxi.service import TaxiService, calculate_price


NOW = datetime(2026, 8, 11, 8, 0, tzinfo=UTC)


class AsyncStore:
    def __init__(self, sync: Session):
        self.sync = sync

    async def get(self, model, identity, **kwargs):
        return self.sync.get(model, identity, **kwargs)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def execute(self, statement):
        return self.sync.execute(statement)

    def add(self, row):
        self.sync.add(row)

    async def flush(self):
        self.sync.flush()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()

    def get_bind(self):
        return self.sync.get_bind()


def account(account_id: int, name: str) -> tuple[Account, UserProfile]:
    return (
        Account(
            id=account_id,
            account_type=AccountType.USER,
            login=f"taxi-user-{account_id}",
            password_hash="hash",
            status="active",
            telegram_user_id=None,
            created_at=NOW,
            updated_at=NOW,
        ),
        UserProfile(
            account_id=account_id,
            name=name,
            phone=f"+9989000000{account_id}",
            public_username=f"taxi_{account_id}",
            region="", district="", mahalla="",
            latitude=None, longitude=None, location_exact=False,
            avatar_object_key="", avatar_x=50, avatar_y=50, avatar_zoom=1,
            followers_count=0, following_count=0, has_business=False,
            dashboard_snapshot={}, recent_activity=[], specialist_profile={},
            cabinet_payload={},
        ),
    )


def service_store():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__, UserProfile.__table__,
            TaxiDriver.__table__, TaxiRide.__table__,
        ),
    )
    sync = Session(engine, expire_on_commit=False)
    sync.add_all((*account(1, "Mijoz"), *account(2, "Haydovchi")))
    sync.commit()
    store = AsyncStore(sync)

    @asynccontextmanager
    async def sessions():
        yield store

    return TaxiService(sessions, now_provider=lambda: NOW), sync, engine


def test_price_keeps_v1656_minimum_and_500_som_rounding():
    assert calculate_price("taxi", 1) == 9000
    assert calculate_price("taxi", 3.6) == 12_000
    assert calculate_price("dostavka", 3) == 17_500
    assert calculate_price("taxi", None) is None


@pytest.mark.asyncio
async def test_driver_validation_and_atomic_accept_commission_flow():
    service, sync, engine = service_store()
    try:
        with pytest.raises(ApiError) as missing_car:
            await service.save_driver(
                user_account_id=2,
                body=DriverWrite(phone="+99890", service="taxi"),
            )
        assert missing_car.value.message == (
            "Taxi uchun mashina rusumi, raqami va rangini to'ldiring."
        )

        await service.save_driver(
            user_account_id=2,
            body=DriverWrite(
                phone="+998901234567",
                service="both",
                car_model="Cobalt",
                car_plate="01 A 123 BC",
                car_color="oq",
            ),
        )
        driver = sync.scalar(
            TaxiDriver.__table__.select().where(TaxiDriver.user_account_id == 2)
        )
        sync.query(TaxiDriver).filter_by(user_account_id=2).update({"balance": 2_000})
        sync.commit()

        created = await service.create_ride(
            customer_account_id=1,
            body=RideCreate(
                kind="taxi",
                from_addr="A",
                to_addr="B",
                from_lat=41.30,
                from_lng=69.20,
                to_lat=41.31,
                to_lng=69.21,
                dist_km=3.6,
                dur_min=8,
            ),
        )
        accepted = await service.accept_ride(
            user_account_id=2,
            ride_id=created.id,
        )

        assert accepted.ride.status == "accepted"
        assert accepted.commission == 1_000
        assert accepted.balance == 1_000
        assert accepted.available is False
        assert accepted.ride.price == 12_000

        with pytest.raises(ApiError) as duplicate:
            await service.create_ride(
                customer_account_id=1,
                body=RideCreate(
                    kind="taxi", from_addr="A", to_addr="B",
                    from_lat=41.3, from_lng=69.2,
                ),
            )
        assert duplicate.value.message == "Sizda hali tugamagan zakaz bor."
    finally:
        sync.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_taxi_and_delivery_status_sequences_remain_separate():
    service, sync, engine = service_store()
    try:
        await service.save_driver(
            user_account_id=2,
            body=DriverWrite(
                phone="+998901234567", service="both", car_model="Cobalt",
                car_plate="01 A 123 BC", car_color="oq",
            ),
        )
        sync.query(TaxiDriver).filter_by(user_account_id=2).update({"balance": 5_000})
        sync.commit()
        ride = await service.create_ride(
            customer_account_id=1,
            body=RideCreate(
                kind="taxi", from_addr="A", to_addr="B",
                from_lat=41.3, from_lng=69.2,
            ),
        )
        await service.accept_ride(user_account_id=2, ride_id=ride.id)

        with pytest.raises(ApiError):
            await service.update_status(
                user_account_id=2, ride_id=ride.id, new_status="completed"
            )
        for status in ("arrived", "ongoing", "completed"):
            result = await service.update_status(
                user_account_id=2, ride_id=ride.id, new_status=status
            )
        assert result.status == "completed"
        assert sync.query(TaxiDriver).filter_by(user_account_id=2).one().available is True
    finally:
        sync.close()
        engine.dispose()


def test_taxi_tables_have_relational_and_concurrency_guards():
    indexes = {
        index.name
        for model in (TaxiDriver, TaxiRide)
        for index in model.__table__.indexes
    }
    assert "uq_taxi_drivers_user" in indexes
    assert "uq_taxi_rides_active_customer" in indexes
    assert "uq_taxi_rides_active_driver" in indexes
    assert TaxiRide.__table__.c.customer_account_id.foreign_keys
    assert TaxiRide.__table__.c.driver_id.foreign_keys


@pytest.mark.asyncio
async def test_ready_delivery_order_creates_one_linked_driver_job():
    business = SimpleNamespace(
        name="Muhr",
        address="Qumqo'rg'on",
        latitude=37.82,
        longitude=67.58,
    )

    class LinkSession:
        def __init__(self):
            self.added = []

        async def scalar(self, _statement):
            return None

        async def get(self, model, _identity):
            from app.profiles.model import BusinessProfile
            assert model is BusinessProfile
            return business

        def add(self, row):
            row.id = 31
            self.added.append(row)

        async def flush(self):
            return None

    session = LinkSession()
    service, sync, engine = service_store()
    order = SimpleNamespace(
        id=91,
        order_type="delivery",
        provider_kind="business",
        provider_account_id=7,
        delivery_lat=37.84,
        delivery_lng=67.60,
        address="Mijoz manzili",
        title="Ikki quti",
    )
    try:
        await service.after_order_ready(session, order)
        ride = session.added[0]
        assert ride.kind == "dostavka"
        assert ride.source_order_id == 91
        assert ride.customer_account_id == 7
        assert ride.from_addr == "Muhr, Qumqo'rg'on"
        assert ride.to_addr == "Mijoz manzili"
        assert ride.dist_km > 0
    finally:
        sync.close()
        engine.dispose()
