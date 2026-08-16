from contextlib import asynccontextmanager
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.db.base import Base
from app.listings.model import Listing  # noqa: F401
from app.notifications.model import (
    Notification,
    NotificationFilter,
    NotificationPreference,
    PushDevice,
    PushOutbox,
)
from app.notifications.push_worker import PendingPush, process_push_batch
from app.notifications.repository import NotificationRepository
from app.notifications.schemas import (
    NotificationFilterWrite,
    NotificationPreferenceWrite,
    PushDeviceWrite,
)
from app.notifications.service import NotificationService, price_number
from app.orders.model import Order  # noqa: F401
from app.profiles.model import ProfileLink

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)


def module(name: str):
    return import_module(f"app.notifications.{name}")


def test_notification_models_normalize_preferences_filters_devices_and_outbox():
    model = module("model")

    assert model.Notification.__tablename__ == "notifications"
    assert model.NotificationPreference.__tablename__ == "notification_preferences"
    assert model.NotificationFilter.__tablename__ == "notification_filters"
    assert model.PushDevice.__tablename__ == "push_devices"
    assert model.PushOutbox.__tablename__ == "push_outbox"
    assert model.Notification.__table__.c.listing_id.foreign_keys
    assert model.PushOutbox.__table__.c.notification_id.foreign_keys
    indexes = {index.name for index in model.Notification.__table__.indexes}
    assert "uq_notifications_owner_event" in indexes
    assert "ix_notifications_owner_actionable" in indexes
    assert "ix_notifications_owner_listing" in indexes


def test_notification_schemas_keep_v1656_filter_and_device_limits():
    body = NotificationFilterWrite(
        cat="uy",
        region="  Toshkent shahri ",
        district=" Chilonzor tumani ",
        price_min=1_000,
        price_max=5_000,
        keyword=" hovli ",
    )
    assert body.region == "Toshkent shahri"
    assert body.district == "Chilonzor tumani"
    assert body.keyword == "hovli"

    with pytest.raises(ValidationError):
        NotificationFilterWrite(cat="uy", price_min=10, price_max=5)
    with pytest.raises(ValidationError):
        PushDeviceWrite(token="short", platform="android")


def test_notification_price_parser_matches_legacy_filter_notation():
    assert price_number("12 mln so‘m") == 12_000_000
    assert price_number("450 ming") == 450_000
    assert price_number("1 250 000 so‘m") == 1_250_000
    assert price_number("Kelishiladi") is None


def test_notifications_router_exposes_list_actions_preferences_filters_and_devices():
    routes = {
        (route.path, method)
        for route in module("router").router.routes
        for method in (route.methods or set())
    }

    expected = {
        ("/api/v1/notifications", "GET"),
        ("/api/v1/notifications/actions", "GET"),
        ("/api/v1/notifications/{notification_id}/read", "PUT"),
        ("/api/v1/notifications/read-all", "PUT"),
        ("/api/v1/notifications/preferences", "GET"),
        ("/api/v1/notifications/preferences", "PUT"),
        ("/api/v1/notifications/filters", "GET"),
        ("/api/v1/notifications/filters", "POST"),
        ("/api/v1/notifications/filters/{filter_id}", "DELETE"),
        ("/api/v1/notifications/devices", "POST"),
        ("/api/v1/notifications/devices", "DELETE"),
        ("/api/v1/notifications/push-status", "GET"),
    }
    assert expected <= routes


def test_notifications_migration_backfills_legacy_json_idempotently():
    migration = ROOT / "migrations" / "versions" / "0033_notifications_v1656.py"
    source = migration.read_text(encoding="utf-8")
    upper = source.upper()

    assert 'revision = "0033_notifications_v1656"' in source
    assert 'down_revision = "0032_reviews"' in source
    for table in (
        "notification_preferences",
        "notification_filters",
        "push_devices",
        "push_outbox",
    ):
        assert table in source
    assert "cabinet_records" in source
    assert "cabinet_payload" in source
    assert "notify_filters" in source
    assert "push_preferences" in source
    assert "DISTINCT ON" in upper
    assert "ON CONFLICT" in upper
    assert "medical_queue_id" in source
    assert "dining_order_id" in source


def test_notifications_are_registered_in_app_metadata_and_paid_activation():
    main_source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    env_source = (ROOT / "migrations" / "env.py").read_text(encoding="utf-8")
    activation_source = (ROOT / "app" / "listings" / "activation.py").read_text(
        encoding="utf-8"
    )

    assert "notification_service" in main_source
    assert "notifications_router" in main_source
    assert "app.include_router(notifications_router)" in main_source
    assert "from app.notifications import model as notifications_model" in env_source
    assert "notify_listing_published" in activation_source


class AsyncStore:
    def __init__(self, sync: Session) -> None:
        self.sync = sync

    def add(self, value):
        self.sync.add(value)

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def flush(self):
        self.sync.flush()

    async def commit(self):
        self.sync.commit()

    def get_bind(self):
        return self.sync.get_bind()


def account(identifier: int, account_type: AccountType) -> Account:
    return Account(
        id=identifier,
        account_type=account_type,
        login=f"notify-{account_type.value}-{identifier}",
        password_hash="hash",
        telegram_user_id=identifier if account_type is AccountType.USER else None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_notification_service_lists_marks_filters_and_queues_linked_push():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            ProfileLink.__table__,
            Notification.__table__,
            NotificationPreference.__table__,
            NotificationFilter.__table__,
            PushDevice.__table__,
            PushOutbox.__table__,
        ),
    )
    sync = Session(engine, expire_on_commit=False)
    sync.add_all(
        [
            account(70, AccountType.USER),
            account(7, AccountType.BUSINESS),
            ProfileLink(user_account_id=70, business_account_id=7, created_at=NOW),
        ]
    )
    sync.commit()
    store = AsyncStore(sync)

    @asynccontextmanager
    async def sessions():
        yield store

    service = NotificationService(
        sessions,
        now_provider=lambda: NOW,
        push_configured=True,
    )
    repository = NotificationRepository()
    device = await service.register_device(
        account_id=70,
        account_type=AccountType.USER,
        body=PushDeviceWrite(
            token="firebase-token-1234567890",
            platform="android",
            device_name="Pixel",
            app_version="1656",
        ),
    )
    assert device.device_id > 0

    await repository.append(
        store,
        account_id=7,
        account_type="business",
        row={
            "event_key": "order:11:new",
            "title": "Yangi buyurtma",
            "body": "Buyurtma #11",
            "order_id": None,
            "action_type": "view_order",
            "profile_kind": "user",
            "profile_public_id": "u_1234567890abcdef",
            "requires_action": 1,
            "created_at": int(NOW.timestamp()),
        },
    )
    await store.commit()

    listed = await service.list(
        account_id=7,
        account_type=AccountType.BUSINESS,
    )
    assert listed.unread == 1
    assert listed.items[0].title == "Yangi buyurtma"
    assert listed.items[0].profile_kind == "user"
    assert listed.items[0].profile_public_id == "u_1234567890abcdef"
    assert (
        await service.actions(
            account_id=7,
            account_type=AccountType.BUSINESS,
        )
    ).count == 1
    assert sync.scalar(select(func.count(PushOutbox.id))) == 1

    await service.mark_read(
        notification_id=listed.items[0].id,
        account_id=7,
        account_type=AccountType.BUSINESS,
    )
    assert (
        await service.list(
            account_id=7,
            account_type=AccountType.BUSINESS,
        )
    ).unread == 0

    preference = await service.save_preference(
        account_id=7,
        account_type=AccountType.BUSINESS,
        body=NotificationPreferenceWrite(enabled=False, orders_enabled=False),
    )
    assert preference.enabled is False

    created_filter = await service.add_filter(
        account_id=70,
        account_type=AccountType.USER,
        body=NotificationFilterWrite(
            cat="uy",
            region="Toshkent shahri",
            district="",
            price_min=100_000,
            price_max=2_000_000,
            keyword="hovli",
        ),
    )
    filters = await service.filters(
        account_id=70,
        account_type=AccountType.USER,
    )
    assert [row.id for row in filters] == [created_filter.id]
    await service.remove_filter(
        filter_id=created_filter.id,
        account_id=70,
        account_type=AccountType.USER,
    )
    assert (
        await service.filters(
            account_id=70,
            account_type=AccountType.USER,
        )
        == []
    )

    status = await service.push_status(
        account_id=7,
        account_type=AccountType.BUSINESS,
    )
    assert status.configured is True
    assert (status.active_devices, status.pending) == (1, 1)

    class FakeDatabase:
        @asynccontextmanager
        async def session(self):
            yield store

    class FakeSender:
        def __init__(self):
            self.pushes: list[PendingPush] = []

        async def send(self, push: PendingPush) -> str:
            self.pushes.append(push)
            return "firebase-message-1"

    sender = FakeSender()
    assert (
        await process_push_batch(
            FakeDatabase(),  # type: ignore[arg-type]
            sender,
            now=int(NOW.timestamp()),
        )
        == 1
    )
    assert sender.pushes[0].data["notification_id"] == str(listed.items[0].id)
    assert sync.scalar(select(PushOutbox.status)) == "sent"
