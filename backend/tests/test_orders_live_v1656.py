from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.catalog.model import CatalogGroup, CatalogItem
from app.cabinet_records.model import CabinetRecord, CabinetRecordField, CabinetResource
from app.cash_register.model import CashReceipt, CashReceiptCounter, CashReceiptLine
from app.cash_register.service import CashRegisterService
from app.core.errors import ApiError
from app.db.base import Base
from app.debt_ledger.model import Debtor, DebtTransaction
from app.debt_ledger.service import DebtLedgerService
from app.legacy_migration.model import OwnerState, ReviewState
from app.inventory.model import (
    InventoryItem,
    StockBatch,
    StockBatchConsumption,
    StockMove,
)
from app.inventory.service import InventoryService
from app.listings.model import Listing
from app.notifications.model import Notification
from app.orders.model import Order, OrderItem, OrderMessage
from app.orders.repository import OrderRepository
from app.orders.router import router as orders_router
from app.orders.schemas import (
    OrderCreate,
    OrderCreateItem,
    OrderMessageCreate,
    OrderPaymentDecision,
    OrderProblemCreate,
    OrderProblemSolution,
    OrderStatusChange,
)
from app.orders.service import OrderService
from app.outbox.model import OutboxEvent
from app.profiles.model import BusinessProfile, UserProfile
from app.public_discovery.repository import build_listing_public_id, build_public_id
from app.public_discovery.schemas import PublicResultKind
from app.catalog.repository import build_content_public_id
from app.staff.model import StaffMember


NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


class AsyncStore:
    def __init__(self, session: Session):
        self.sync = session
        self.sequences: dict[str, int] = {}

    def add(self, value):
        self.sync.add(value)

    async def delete(self, value):
        self.sync.delete(value)

    async def flush(self):
        for value in list(self.sync.new):
            if not hasattr(value, "id") or value.id is not None:
                continue
            table = value.__table__.name
            if table not in self.sequences:
                highest = self.sync.scalar(select(func.max(value.__table__.c.id)))
                self.sequences[table] = int(highest or 0)
            self.sequences[table] += 1
            value.id = self.sequences[table]
        self.sync.flush()

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def get(self, model, identity, **_kwargs):
        return self.sync.get(model, identity)

    def get_bind(self):
        return self.sync.get_bind()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


@pytest.fixture
def order_store():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            UserProfile.__table__,
            BusinessProfile.__table__,
            CatalogGroup.__table__,
            CatalogItem.__table__,
            StaffMember.__table__,
            Debtor.__table__,
            CabinetResource.__table__,
            CabinetRecord.__table__,
            CabinetRecordField.__table__,
            Listing.__table__,
            Order.__table__,
            OrderItem.__table__,
            OrderMessage.__table__,
            InventoryItem.__table__,
            StockMove.__table__,
            StockBatch.__table__,
            StockBatchConsumption.__table__,
            CashReceiptCounter.__table__,
            CashReceipt.__table__,
            CashReceiptLine.__table__,
            DebtTransaction.__table__,
            Notification.__table__,
            OutboxEvent.__table__,
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
        Account(
            id=8,
            account_type=AccountType.BUSINESS,
            login="business_8",
            password_hash="hash",
            telegram_user_id=None,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        ),
        UserProfile(
            account_id=5,
            name="Ali",
            phone="+998901234567",
            public_username="ali",
            region="Surxondaryo viloyati",
            district="Qumqo‘rg‘on tumani",
            mahalla="",
            latitude=37.82,
            longitude=67.58,
            location_exact=True,
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
            cabinet_payload={},
        ),
        BusinessProfile(
            account_id=7,
            name="Muhr",
            phone="+998907654321",
            description="",
            public_username="muhr",
            direction="Savdo",
            activity_type="Do‘kon",
            address="Qumqo‘rg‘on",
            latitude=37.81,
            longitude=67.57,
            work_hours={"monday": "09:00-18:00"},
            pay_card="8600123412341234",
            pay_holder="MUHR MCHJ",
            pay_qr_object_key="private/business/7/payment_qr/qr.webp",
            director="",
            tax_id="",
            logo_object_key="",
            logo_x=50,
            logo_y=50,
            logo_zoom=1,
            followers_count=0,
            following_count=0,
            rating_sum=0,
            rating_count=0,
            map_visible=True,
            dashboard_snapshot={},
            recent_activity=[],
            cabinet_payload={},
        ),
        BusinessProfile(
            account_id=8,
            name="Begona biznes",
            phone="",
            description="",
            public_username="begona",
            direction="Savdo",
            activity_type="Do‘kon",
            address="",
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
            followers_count=0,
            following_count=0,
            rating_sum=0,
            rating_count=0,
            map_visible=False,
            dashboard_snapshot={},
            recent_activity=[],
            cabinet_payload={},
        ),
        CatalogItem(
            id=11,
            business_account_id=7,
            source_record_key="101",
            catalog_group_id=None,
            owner_name_snapshot="Muhr",
            name="Ingliz tili",
            price_text="35 000 so'm",
            unit="kg",
            note="Izoh",
            kind="service",
            queue_enabled=False,
            image_object_key="",
            status="active",
            owner_state=OwnerState.LINKED,
            review_state=ReviewState.READY,
            migration_run_id=None,
            created_at=NOW,
            updated_at=NOW,
        ),
        Debtor(
            id=701,
            business_account_id=7,
            legacy_source_id=301,
            name="Vali Karimov",
            phone="+998901112233",
            note="",
            due="",
            created_by_staff_id=None,
            created_at=NOW,
            updated_at=NOW,
        ),
        Debtor(
            id=801,
            business_account_id=8,
            legacy_source_id=302,
            name="Begona qarzdor",
            phone="",
            note="",
            due="",
            created_by_staff_id=None,
            created_at=NOW,
            updated_at=NOW,
        ),
        Listing(
            id=21,
            owner_user_account_id=None,
            owner_business_account_id=7,
            source_record_key="201",
            category="uy",
            title="Hovli sotiladi",
            price_text="200 000 000 so'm",
            description="",
            address="Qumqo‘rg‘on",
            latitude=37.81,
            longitude=67.57,
            visibility="all",
            status="active",
            review_state=ReviewState.READY,
            migration_run_id=None,
            created_at=NOW,
            updated_at=NOW,
        ),
        CatalogItem(
            id=12,
            business_account_id=8,
            source_record_key="102",
            catalog_group_id=None,
            owner_name_snapshot="Begona biznes",
            name="Begona tovar",
            price_text="10 000 so'm",
            note="",
            kind="product",
            queue_enabled=False,
            image_object_key="",
            status="active",
            owner_state=OwnerState.LINKED,
            review_state=ReviewState.READY,
            migration_run_id=None,
            created_at=NOW,
            updated_at=NOW,
        ),
    ))
    session.commit()
    try:
        yield AsyncStore(session)
    finally:
        session.close()
        engine.dispose()


def service_for(store: AsyncStore) -> OrderService:
    @asynccontextmanager
    async def sessions():
        yield store

    return OrderService(sessions, lambda key: f"/media/{key}")


def service_with_repository(
    store: AsyncStore,
    repository: OrderRepository,
) -> OrderService:
    @asynccontextmanager
    async def sessions():
        yield store

    return OrderService(
        sessions,
        lambda key: f"/media/{key}",
        repository=repository,
    )


def service_with_cash(store: AsyncStore) -> OrderService:
    @asynccontextmanager
    async def sessions():
        yield store

    inventory = InventoryService(sessions, now_provider=lambda: NOW)
    debts = DebtLedgerService(sessions, now_provider=lambda: NOW)
    cash = CashRegisterService(
        sessions,
        inventory_service=inventory,
        debt_ledger_service=debts,
        now_provider=lambda: NOW,
    )
    return OrderService(
        sessions,
        lambda key: f"/media/{key}",
        cash_register_service=cash,
        debt_ledger_service=debts,
    )


def create_body(*, item_id: int = 11, order_type: str = "pickup") -> OrderCreate:
    return OrderCreate(
        provider_kind="business",
        provider_public_id=build_public_id(PublicResultKind.BUSINESS, 7),
        items=[OrderCreateItem(
            public_id=build_content_public_id(
                "service" if item_id == 11 else "product",
                item_id,
            ),
            qty=2,
        )],
        phone="+998 90 123 45 67",
        order_type=order_type,
        address="Qumqo‘rg‘on",
        desired_time="14:00",
        delivery_lat=37.82 if order_type == "delivery" else None,
        delivery_lng=67.58 if order_type == "delivery" else None,
        note="Qo‘ng‘iroq qiling",
    )


def test_order_models_have_v1656_constraints_and_foreign_key_indexes():
    assert Order.__table__.c.id.type.python_type is int
    assert Order.__table__.c.legacy_source_id.nullable is True
    assert OrderItem.__table__.c.order_id.foreign_keys
    assert OrderMessage.__table__.c.order_id.foreign_keys
    index_names = {index.name for index in Order.__table__.indexes}
    assert "ix_orders_customer_created" in index_names
    assert "ix_orders_provider_created" in index_names
    assert "ix_orders_provider_unread" in index_names
    assert "ix_orders_customer_unread" in index_names


@pytest.mark.asyncio
async def test_create_order_snapshots_items_and_is_visible_to_both_sides(order_store):
    service = service_for(order_store)

    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=create_body(),
    )

    assert created.id > 0
    assert created.title == "Ingliz tili"
    assert created.order_category == "service"
    assert created.status == "new"
    assert created.payment_status == ""
    notification = order_store.sync.scalar(select(Notification).where(
        Notification.account_id == 7,
        Notification.account_type == "business",
        Notification.event_key == f"order:{created.id}:created",
    ))
    assert notification is not None
    assert notification.title == "Yangi buyurtma keldi"
    assert notification.body == "Buyurtmani ko'rib, qabul qiling."
    assert notification.order_id == created.id
    assert notification.is_read is False
    assert created.total_amount == 70000
    assert created.items[0].name == "Ingliz tili"
    assert created.items[0].price == "35 000 so'm"
    assert created.items[0].qty == 2
    assert created.customer_name == "Ali"
    assert created.provider_name == "Muhr"
    assert created.pay_card == "8600123412341234"

    customer_rows = await service.list_my(
        account_id=5,
        account_type=AccountType.USER,
    )
    provider_rows = await service.list_inbox(
        account_id=7,
        account_type=AccountType.BUSINESS,
    )
    assert [row.id for row in customer_rows] == [created.id]
    assert [row.id for row in provider_rows] == [created.id]
    assert customer_rows[0].view == "customer"
    assert provider_rows[0].view == "provider"

    events = list(order_store.sync.scalars(select(OutboxEvent).order_by(OutboxEvent.id)))
    assert [event.topic for event in events] == ["order.created"]


@pytest.mark.asyncio
async def test_create_order_blocks_self_order_foreign_items_and_missing_delivery_point(order_store):
    service = service_for(order_store)

    with pytest.raises(ApiError, match="O'zingizga buyurtma bera olmaysiz"):
        await service.create(
            account_id=7,
            account_type=AccountType.BUSINESS,
            body=create_body(),
        )

    with pytest.raises(ApiError, match="Mahsulot/xizmat bu biznesga tegishli emas"):
        await service.create(
            account_id=5,
            account_type=AccountType.USER,
            body=create_body(item_id=12),
        )

    body = create_body(order_type="delivery").model_copy(
        update={"delivery_lat": None, "delivery_lng": None}
    )
    with pytest.raises(ApiError, match="Yetkazib berish joyini xaritada belgilang"):
        await service.create(
            account_id=5,
            account_type=AccountType.USER,
            body=body,
        )

    no_phone = create_body(order_type="delivery").model_copy(
        update={"phone": ""}
    )
    with pytest.raises(ApiError, match="Telefon raqam kiritish kerak"):
        await service.create(
            account_id=5,
            account_type=AccountType.USER,
            body=no_phone,
        )


@pytest.mark.asyncio
async def test_payment_problem_chat_handoff_and_received_follow_v1656(order_store):
    service = service_for(order_store)
    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=create_body(),
    )

    accepted = await service.change_status(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
        body=OrderStatusChange(status="accepted"),
    )
    assert accepted.status == "accepted"
    assert accepted.payment_status == "pending"
    accepted_notification = order_store.sync.scalar(select(Notification).where(
        Notification.account_id == 5,
        Notification.account_type == "user",
        Notification.event_key == f"order:{created.id}:accepted",
    ))
    assert accepted_notification is not None
    assert accepted_notification.title == "Buyurtma qabul qilindi"
    assert accepted_notification.action_type == "make_payment"
    await service.mark_seen(
        order_id=created.id,
        account_id=5,
        account_type=AccountType.USER,
    )
    order_store.sync.refresh(accepted_notification)
    assert accepted_notification.is_read is True
    unread = order_store.sync.scalar(select(func.count(Notification.id)).where(
        Notification.account_id == 5,
        Notification.account_type == "user",
        Notification.is_read.is_(False),
    ))
    assert unread == 0

    with pytest.raises(ApiError, match="Avval to'lov cheki rasmini"):
        await service.submit_payment(
            order_id=created.id,
            account_id=5,
            account_type=AccountType.USER,
        )

    receipt = await service.send_message(
        order_id=created.id,
        account_id=5,
        account_type=AccountType.USER,
        body=OrderMessageCreate(
            text="To‘lov cheki",
            media_type="photo",
            object_key="private/user/5/order_chat_image/receipt.webp",
            file_name="receipt.webp",
        ),
    )
    submitted = await service.submit_payment(
        order_id=created.id,
        account_id=5,
        account_type=AccountType.USER,
    )
    assert submitted.payment_status == "submitted"
    assert submitted.receipt_message_id == receipt.id
    assert submitted.chat_count == 1
    assert submitted.last_chat == "To‘lov cheki"

    disputed = await service.open_problem(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
        body=OrderProblemCreate(reason="receipt_unreadable", note="Rasm xira"),
    )
    assert disputed.problem_open is True
    assert disputed.payment_status == "disputed"

    recheck = await service.choose_problem_solution(
        order_id=created.id,
        account_id=5,
        account_type=AccountType.USER,
        body=OrderProblemSolution(solution="new_receipt"),
    )
    assert recheck.problem_solution == "new_receipt"
    assert recheck.payment_status == "recheck"

    reply = await service.send_message(
        order_id=created.id,
        account_id=5,
        account_type=AccountType.USER,
        body=OrderMessageCreate(text="Yangisi", reply_to_id=receipt.id),
    )
    assert reply.reply is not None
    assert reply.reply.id == receipt.id
    assert reply.reply.text == "To‘lov cheki"
    assert reply.reply.media_type == "photo"
    assert reply.reply.sender_name == "Ali"
    edited = await service.edit_message(
        order_id=created.id,
        message_id=reply.id,
        account_id=5,
        account_type=AccountType.USER,
        text="Yangi chek yuboraman",
    )
    assert edited.text == "Yangi chek yuboraman"
    deleted = await service.delete_message(
        order_id=created.id,
        message_id=reply.id,
        account_id=5,
        account_type=AccountType.USER,
    )
    assert deleted.is_deleted is True
    assert deleted.text == ""

    await service.submit_payment(
        order_id=created.id,
        account_id=5,
        account_type=AccountType.USER,
    )
    preparing = await service.set_payment(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
        body=OrderPaymentDecision(status="confirmed"),
    )
    assert preparing.status == "preparing"
    assert preparing.payment_status == "confirmed"
    assert preparing.problem_open is False

    ready = await service.change_status(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
        body=OrderStatusChange(status="tayyor"),
    )
    assert ready.status == "tayyor"
    handed = await service.handoff(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
    )
    assert handed.status == "pickup_waiting_customer"
    done = await service.received(
        order_id=created.id,
        account_id=5,
        account_type=AccountType.USER,
    )
    assert done.status == "done"

    listed = (await service.list_my(
        account_id=5,
        account_type=AccountType.USER,
    ))[0]
    assert listed.chat_count == 3
    assert listed.last_chat == "✅ To'lov tasdiqlandi. Rahmat!"
    assert listed.last_chat_at is not None

    topics = list(order_store.sync.scalars(
        select(OutboxEvent.topic).order_by(OutboxEvent.id)
    ))
    assert topics == [
        "order.created",
        "order.status_changed",
        "order.message_created",
        "order.payment_submitted",
        "order.problem_opened",
        "order.problem_solution_selected",
        "order.message_created",
        "order.message_edited",
        "order.message_deleted",
        "order.payment_submitted",
        "order.payment_confirmed",
        "order.status_changed",
        "order.handed_off",
        "order.completed",
    ]


@pytest.mark.asyncio
async def test_accepted_order_debt_is_idempotent_and_links_cash_on_handoff(order_store):
    service = service_with_cash(order_store)
    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=create_body(),
    )
    await service.change_status(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
        body=OrderStatusChange(status="accepted"),
    )

    with pytest.raises(ApiError) as foreign:
        await service.set_payment(
            order_id=created.id,
            account_id=7,
            account_type=AccountType.BUSINESS,
            body=OrderPaymentDecision(status="debt", debtor_id=801),
        )
    assert foreign.value.code == "debt_debtor_required"

    preparing = await service.set_payment(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
        body=OrderPaymentDecision(status="debt", debtor_id=701),
    )
    assert preparing.status == "preparing"
    assert preparing.payment_status == "confirmed"
    assert preparing.pay_type == "qarz"
    assert preparing.debtor_id == 701

    repeated = await service.set_payment(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
        body=OrderPaymentDecision(status="debt", debtor_id=701),
    )
    assert repeated.pay_type == "qarz"
    assert order_store.sync.scalar(
        select(func.count(DebtTransaction.id))
    ) == 1

    await service.change_status(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
        body=OrderStatusChange(status="tayyor"),
    )
    await service.handoff(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
    )

    receipt = order_store.sync.scalar(
        select(CashReceipt).where(CashReceipt.order_id == created.id)
    )
    transaction = order_store.sync.scalar(select(DebtTransaction))
    assert receipt is not None and receipt.pay_type == "qarz"
    assert receipt.debtor_id == 701
    assert receipt.debtor_name_snapshot == "Vali Karimov"
    assert transaction is not None
    assert transaction.amount == 70_000
    assert transaction.order_id == created.id
    assert transaction.cash_receipt_id == receipt.id


@pytest.mark.asyncio
async def test_order_debt_requires_payment_permission_and_accepted_status(order_store):
    service = service_with_cash(order_store)
    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=create_body(),
    )
    with pytest.raises(ApiError) as status_error:
        await service.set_payment(
            order_id=created.id,
            account_id=7,
            account_type=AccountType.BUSINESS,
            body=OrderPaymentDecision(status="debt", debtor_id=701),
        )
    assert status_error.value.code == "order_debt_status_invalid"

    await service.change_status(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
        body=OrderStatusChange(status="accepted"),
    )
    with pytest.raises(ApiError) as permission_error:
        await service.set_payment(
            order_id=created.id,
            account_id=7,
            account_type=AccountType.BUSINESS,
            body=OrderPaymentDecision(status="debt", debtor_id=701),
            actor_staff_id=99,
            permissions=("buyurtma",),
        )
    assert permission_error.value.code == "staff_permission_required"


@pytest.mark.asyncio
async def test_delivery_handoff_waiting_seller_moves_order_to_in_delivery(order_store):
    service = service_for(order_store)
    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=create_body(order_type="delivery"),
    )
    delivery = order_store.sync.get(Order, created.id)
    delivery.status = "handoff_waiting_seller"
    delivery.payment_status = "confirmed"
    order_store.sync.commit()

    handed = await service.handoff(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
    )

    assert handed.status == "in_delivery"
    assert handed.seller_completed_at is not None
    event = order_store.sync.scalar(
        select(OutboxEvent)
        .where(OutboxEvent.topic == "order.handed_off")
        .order_by(OutboxEvent.id.desc())
    )
    assert event is not None
    assert event.payload["status"] == "in_delivery"

    delivery.status = "delivered_waiting_customer"
    order_store.sync.commit()
    received = await service.received(
        order_id=created.id,
        account_id=5,
        account_type=AccountType.USER,
    )
    assert received.status == "done"
    assert received.customer_received_at is not None


@pytest.mark.asyncio
async def test_handoff_posts_cash_receipt_in_the_order_transaction(order_store):
    service = service_with_cash(order_store)
    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=create_body(),
    )
    order = order_store.sync.get(Order, created.id)
    order.status = "tayyor"
    order.payment_status = "confirmed"
    order.pay_type = "karta"
    order_store.sync.commit()

    handed = await service.handoff(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
        actor_staff_id=44,
    )

    assert handed.status == "pickup_waiting_customer"
    receipt = order_store.sync.scalar(
        select(CashReceipt).where(CashReceipt.order_id == created.id)
    )
    assert receipt is not None
    assert receipt.source == "order"
    assert receipt.pay_type == "karta"
    assert receipt.created_by_staff_id == 44
    lines = list(order_store.sync.scalars(
        select(CashReceiptLine).where(CashReceiptLine.receipt_id == receipt.id)
    ))
    assert len(lines) == 1
    assert lines[0].total == 70000


@pytest.mark.asyncio
async def test_handoff_fifo_failure_rolls_back_order_and_cash(order_store):
    service = service_with_cash(order_store)
    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=create_body(),
    )
    order = order_store.sync.get(Order, created.id)
    order.status = "tayyor"
    order.payment_status = "confirmed"
    order.pay_type = "karta"
    order_store.sync.add(InventoryItem(
        id=301,
        business_account_id=7,
        catalog_item_id=11,
        legacy_source_id=101,
        track_stock=True,
        stock_type="ready_food",
        stock_qty=0,
        cost_price=0,
        min_qty=0,
        fifo_initialized=True,
        created_at=NOW,
        updated_at=NOW,
    ))
    order_store.sync.commit()

    with pytest.raises(ApiError) as error:
        await service.handoff(
            order_id=created.id,
            account_id=7,
            account_type=AccountType.BUSINESS,
        )
    assert error.value.code == "inventory_fifo_insufficient"
    order_store.sync.expire_all()
    assert order_store.sync.get(Order, created.id).status == "tayyor"
    assert order_store.sync.scalar(select(func.count(CashReceipt.id))) == 0


@pytest.mark.asyncio
async def test_stranger_cannot_read_or_mutate_order(order_store):
    service = service_for(order_store)
    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=create_body(),
    )

    assert await service.list_inbox(
        account_id=8,
        account_type=AccountType.BUSINESS,
    ) == []
    with pytest.raises(ApiError, match="Buyurtma topilmadi"):
        await service.change_status(
            order_id=created.id,
            account_id=8,
            account_type=AccountType.BUSINESS,
            body=OrderStatusChange(status="accepted"),
        )
    with pytest.raises(ApiError, match="Buyurtma topilmadi"):
        await service.list_messages(
            order_id=created.id,
            account_id=8,
            account_type=AccountType.BUSINESS,
        )


@pytest.mark.asyncio
async def test_generic_business_order_and_provider_cancellation_match_v1656(order_store):
    service = service_for(order_store)
    body = create_body().model_copy(update={
        "items": [],
        "title": "Buyurtma: Muhr",
    })

    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=body,
    )
    assert created.title == "Buyurtma: Muhr"
    assert created.items == []
    assert created.total_amount == 0

    await service.change_status(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
        body=OrderStatusChange(status="accepted"),
    )
    cancelled = await service.change_status(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
        body=OrderStatusChange(status="cancelled"),
    )
    assert cancelled.status == "cancelled"


@pytest.mark.asyncio
async def test_generic_order_does_not_query_the_catalog(order_store):
    class CatalogQueryGuard(OrderRepository):
        async def catalog_items_by_public_ids(self, session, *, public_ids):
            raise AssertionError("Bo'sh buyurtmada katalog so'rovi bajarilmasligi kerak.")

        async def all_catalog_items(self, session):
            raise AssertionError("Butun katalogni yuklash taqiqlangan.")

    service = service_with_repository(order_store, CatalogQueryGuard())
    body = create_body().model_copy(update={
        "items": [],
        "title": "Buyurtma: Muhr",
    })

    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=body,
    )

    assert created.title == "Buyurtma: Muhr"
    assert created.items == []


@pytest.mark.asyncio
async def test_catalog_order_queries_only_requested_public_ids(order_store):
    expected = build_content_public_id("service", 11)

    class CatalogQueryGuard(OrderRepository):
        requested: list[str] | None = None

        async def catalog_items_by_public_ids(self, session, *, public_ids):
            self.requested = list(public_ids)
            return [order_store.sync.get(CatalogItem, 11)]

        async def all_catalog_items(self, session):
            raise AssertionError("Butun katalogni yuklash taqiqlangan.")

    repository = CatalogQueryGuard()
    service = service_with_repository(order_store, repository)

    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=create_body(),
    )

    assert repository.requested == [expected]
    assert created.items[0].name == "Ingliz tili"


@pytest.mark.asyncio
async def test_listing_order_uses_listing_title_and_validates_owner(order_store):
    service = service_for(order_store)
    body = create_body().model_copy(update={
        "items": [],
        "title": "",
        "listing_public_id": build_listing_public_id(21),
    })

    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=body,
    )
    assert created.title == "Hovli sotiladi"
    assert created.items == []


def test_order_router_exposes_every_v1656_core_endpoint():
    paths = {
        (route.path, method)
        for route in orders_router.routes
        for method in (route.methods or set())
    }
    assert ("/api/v1/orders", "POST") in paths
    assert ("/api/v1/orders/my", "GET") in paths
    assert ("/api/v1/orders/inbox", "GET") in paths
    assert ("/api/v1/orders/{order_id}/seen", "PUT") in paths
    assert ("/api/v1/orders/{order_id}/status", "PUT") in paths
    assert ("/api/v1/orders/{order_id}/payment/submit", "POST") in paths
    assert ("/api/v1/orders/{order_id}/payment", "POST") in paths
    assert ("/api/v1/orders/{order_id}/problem", "POST") in paths
    assert ("/api/v1/orders/{order_id}/problem/solution", "PUT") in paths
    assert ("/api/v1/orders/{order_id}/handoff", "POST") in paths
    assert ("/api/v1/orders/{order_id}/received", "POST") in paths
    assert ("/api/v1/orders/{order_id}/chat", "GET") in paths
    assert ("/api/v1/orders/{order_id}/chat", "POST") in paths
    assert ("/api/v1/orders/{order_id}/chat/image", "POST") in paths
    assert ("/api/v1/orders/{order_id}/chat/{message_id}", "PUT") in paths
    assert ("/api/v1/orders/{order_id}/chat/{message_id}", "DELETE") in paths


@pytest.mark.asyncio
async def test_rejected_payment_is_saved_and_system_message_is_written(order_store):
    service = service_for(order_store)
    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=create_body(),
    )
    await service.change_status(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
        body=OrderStatusChange(status="accepted"),
    )
    await service.send_message(
        order_id=created.id,
        account_id=5,
        account_type=AccountType.USER,
        body=OrderMessageCreate(
            media_type="photo",
            object_key="private/user/5/order_chat_image/receipt.webp",
        ),
    )
    await service.submit_payment(
        order_id=created.id,
        account_id=5,
        account_type=AccountType.USER,
    )

    rejected = await service.set_payment(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
        body=OrderPaymentDecision(status="rejected"),
    )
    assert rejected.payment_status == "rejected"
    messages = await service.list_messages(
        order_id=created.id,
        account_id=5,
        account_type=AccountType.USER,
    )
    assert messages[-1].text == (
        "❌ To'lov tasdiqlanmadi. Iltimos, to'lovni tekshiring yoki qayta yuboring."
    )


@pytest.mark.asyncio
async def test_chat_response_contains_order_side_and_other_profile(order_store):
    service = service_for(order_store)
    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=create_body(),
    )
    chat = await service.chat(
        order_id=created.id,
        account_id=5,
        account_type=AccountType.USER,
    )

    assert chat.ok is True
    assert chat.side == "customer"
    assert chat.order.id == created.id
    assert chat.other.side == "provider"
    assert chat.other.name == "Muhr"
    assert chat.other.public_id == build_public_id(
        PublicResultKind.BUSINESS,
        7,
    )
    assert chat.messages == []


@pytest.mark.asyncio
async def test_fractional_units_are_deduplicated_and_keep_half_quantity(order_store):
    service = service_for(order_store)
    item_public_id = build_content_public_id("service", 11)
    body = create_body().model_copy(update={
        "items": [
            OrderCreateItem(public_id=item_public_id, qty=0.25),
            OrderCreateItem(public_id=item_public_id, qty=0.25),
        ],
    })

    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=body,
    )
    assert len(created.items) == 1
    assert created.items[0].qty == 0.5
    assert created.items[0].unit == "kg"
    assert created.items[0].line_total == 17500
    assert created.total_amount == 17500


@pytest.mark.asyncio
async def test_illegal_status_transitions_return_v1656_conflicts(order_store):
    service = service_for(order_store)
    created = await service.create(
        account_id=5,
        account_type=AccountType.USER,
        body=create_body(),
    )

    with pytest.raises(ApiError, match="faqat qabul qiluvchi kabinet") as customer_accept:
        await service.change_status(
            order_id=created.id,
            account_id=5,
            account_type=AccountType.USER,
            body=OrderStatusChange(status="accepted"),
        )
    assert customer_accept.value.status_code == 403

    with pytest.raises(ApiError, match="faqat Tayyorlanmoqda") as too_early:
        await service.change_status(
            order_id=created.id,
            account_id=7,
            account_type=AccountType.BUSINESS,
            body=OrderStatusChange(status="tayyor"),
        )
    assert too_early.value.status_code == 409

    await service.change_status(
        order_id=created.id,
        account_id=7,
        account_type=AccountType.BUSINESS,
        body=OrderStatusChange(status="accepted"),
    )
    created_row = order_store.sync.get(Order, created.id)
    created_row.status = "preparing"
    order_store.sync.commit()
    with pytest.raises(ApiError, match="To'lov tasdiqlanmaguncha") as unpaid:
        await service.change_status(
            order_id=created.id,
            account_id=7,
            account_type=AccountType.BUSINESS,
            body=OrderStatusChange(status="tayyor"),
        )
    assert unpaid.value.status_code == 409
