from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.cabinet_records.model import (
    CabinetRecord,
    CabinetRecordField,
    CabinetResource,
)
from app.db.base import Base
from app.notifications.model import Notification
from app.notifications.repository import NotificationRepository
from app.orders.model import Order as _Order  # noqa: F401
from app.profiles.router import (
    assembled_cabinet_payload,
    dashboard_with_notification_count,
)


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0011_notifications_relational.py"
)
ORDER_NOTIFICATIONS = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "orders"
    / "notifications.py"
)
ALEMBIC_ENV = MIGRATION.parents[1] / "env.py"
NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


class AsyncStore:
    def __init__(self, session: Session):
        self.sync = session

    def add(self, value):
        self.sync.add(value)

    async def flush(self):
        self.sync.flush()

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    def get_bind(self):
        return self.sync.get_bind()


@pytest.fixture
def notification_store():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            CabinetResource.__table__,
            CabinetRecord.__table__,
            CabinetRecordField.__table__,
            Notification.__table__,
        ),
    )
    session = Session(engine, expire_on_commit=False)
    session.add_all((
        Account(
            id=5,
            account_type=AccountType.USER,
            login="user_5",
            password_hash="hash",
            telegram_user_id=None,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        ),
        Account(
            id=7,
            account_type=AccountType.BUSINESS,
            login="business_7",
            password_hash="hash",
            telegram_user_id=None,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        ),
    ))
    session.commit()
    try:
        yield engine, AsyncStore(session)
    finally:
        session.close()
        engine.dispose()


def test_notification_model_has_owner_event_and_unread_indexes():
    assert Notification.__tablename__ == "notifications"
    assert Notification.__table__.c.account_id.nullable is False
    assert Notification.__table__.c.account_type.nullable is False
    assert Notification.__table__.c.event_key.nullable is False

    indexes = {index.name: index for index in Notification.__table__.indexes}
    assert indexes["uq_notifications_owner_event"].unique is True
    assert indexes["ix_notifications_owner_created"].unique is False
    assert indexes["ix_notifications_owner_unread"].unique is False
    assert indexes["ix_notifications_owner_order"].unique is False


def test_notification_migration_backfills_both_sources_idempotently():
    source = MIGRATION.read_text(encoding="utf-8")
    upper = source.upper()

    assert 'revision = "0011_notifications_relational"' in source
    assert 'down_revision = "0010_public_id_indexed_lookup"' in source
    assert 'op.create_table(\n        "notifications"' in source
    assert "cabinet_resources" in source
    assert "cabinet_records" in source
    assert "cabinet_record_fields" in source
    assert "user_profiles" in source
    assert "business_profiles" in source
    assert "cabinet_payload" in source
    assert "jsonb_array_elements" in source
    assert "legacy_source_id" in source
    assert "INSERT INTO notifications" in source
    assert "ON CONFLICT" in upper
    assert "DO NOTHING" in upper
    assert "uq_notifications_owner_event" in source
    assert "ix_notifications_owner_unread" in source


def test_alembic_metadata_registers_notification_model():
    source = ALEMBIC_ENV.read_text(encoding="utf-8")
    assert "from app.notifications import model as notifications_model" in source


def test_order_hot_path_does_not_lock_or_rewrite_profile_payload():
    source = ORDER_NOTIFICATIONS.read_text(encoding="utf-8")

    assert "NotificationRepository" in source
    assert "with_for_update" not in source
    assert "cabinet_payload" not in source
    assert "CabinetRecordRepository" not in source
    assert "sync_json_fallback" not in source
    assert "BusinessProfile" not in source
    assert "UserProfile" not in source


@pytest.mark.asyncio
async def test_append_is_one_indexed_insert_and_duplicate_event_is_idempotent(
    notification_store,
):
    engine, store = notification_store
    repository = NotificationRepository()
    statements: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        row = {
            "event_key": "order:31:created",
            "title": "Yangi buyurtma keldi",
            "body": "Buyurtmani ko'rib, qabul qiling.",
            "order_id": 31,
            "action_type": "accept_order",
            "requires_action": 1,
            "is_read": 0,
            "created_at": 1785672000,
            "medical_queue_id": 41,
        }
        await repository.append(
            store,
            account_id=7,
            account_type="business",
            row=row,
        )
        await repository.append(
            store,
            account_id=7,
            account_type="business",
            row=row,
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert store.sync.scalar(select(func.count(Notification.id))) == 1
    assert len(statements) == 2
    assert all("INSERT INTO notifications" in statement for statement in statements)
    assert all("user_profiles" not in statement for statement in statements)
    assert all("business_profiles" not in statement for statement in statements)
    assert all("cabinet_" not in statement for statement in statements)

    rows = await repository.list_rows(
        store,
        account_id=7,
        account_type="business",
    )
    assert rows is not None
    assert rows[0]["event_key"] == "order:31:created"
    assert rows[0]["medical_queue_id"] == 41
    assert rows[0]["is_read"] == 0


@pytest.mark.asyncio
async def test_marking_read_updates_only_owner_order_rows(notification_store):
    _engine, store = notification_store
    repository = NotificationRepository()
    for account_id, account_type, event_key, order_id in (
        (5, "user", "order:31:accepted", 31),
        (5, "user", "order:32:accepted", 32),
        (7, "business", "order:31:created", 31),
    ):
        await repository.append(
            store,
            account_id=account_id,
            account_type=account_type,
            row={
                "event_key": event_key,
                "title": "Xabar",
                "body": "Matn",
                "order_id": order_id,
                "is_read": 0,
                "created_at": 1785672000,
            },
        )

    await repository.mark_order_read(
        store,
        account_id=5,
        account_type="user",
        order_id=31,
        read_at=1785672060,
    )

    user_rows = await repository.list_rows(
        store,
        account_id=5,
        account_type="user",
    )
    business_rows = await repository.list_rows(
        store,
        account_id=7,
        account_type="business",
    )
    assert user_rows is not None
    assert business_rows is not None
    assert [row["is_read"] for row in user_rows] == [1, 0]
    assert business_rows[0]["is_read"] == 0
    assert await repository.unread_count(
        store,
        account_id=5,
        account_type="user",
    ) == 1


@pytest.mark.asyncio
async def test_profile_projection_overrides_stale_json_and_counts_relational_unread(
    notification_store,
):
    _engine, store = notification_store
    repository = NotificationRepository()
    for event_key, is_read in (
        ("order:31:accepted", 0),
        ("order:31:ready", 1),
    ):
        await repository.append(
            store,
            account_id=5,
            account_type="user",
            row={
                "event_key": event_key,
                "title": "Xabar",
                "body": "Matn",
                "order_id": 31,
                "is_read": is_read,
                "created_at": 1785672000 + is_read,
            },
        )

    payload = await assembled_cabinet_payload(
        store,
        account_id=5,
        account_type=AccountType.USER,
        fallback={"notifications": [{"id": 999, "is_read": 0}]},
    )
    snapshot = dashboard_with_notification_count(
        SimpleNamespace(dashboard_snapshot={"active_orders": 2, "unread": 99}),
        payload,
    )

    assert [row["event_key"] for row in payload["notifications"]] == [
        "order:31:accepted",
        "order:31:ready",
    ]
    assert snapshot == {"active_orders": 2, "unread": 1}
