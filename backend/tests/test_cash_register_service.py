from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.cash_register.model import CashReceipt, CashReceiptCounter, CashReceiptLine
from app.cash_register.repository import CashRegisterRepository
from app.cash_register.schemas import (
    CashPaymentUpdate,
    CashReceiptCreate,
    CashSaleLineCreate,
)
from app.cash_register.service import CashRegisterService
from app.catalog.model import CatalogGroup, CatalogItem
from app.core.errors import ApiError
from app.db.base import Base
from app.debt_ledger.model import Debtor, DebtTransaction
from app.debt_ledger.schemas import DebtorCreate, DebtTransactionCreate
from app.debt_ledger.service import DebtLedgerService
from app.inventory.model import (
    InventoryItem,
    StockBatch,
    StockBatchConsumption,
    StockMove,
)
from app.inventory.service import InventoryService
from app.legacy_migration.model import OwnerState, ReviewState
from app.listings.model import Listing
from app.orders.model import Order, OrderItem
from app.profiles.model import BusinessProfile
from app.staff.model import StaffMember


NOW = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)


class AsyncStore:
    def __init__(self, sync: Session) -> None:
        self.sync = sync
        self.sequences: dict[str, int] = {}

    def add(self, value):
        self.sync.add(value)

    async def delete(self, value):
        self.sync.delete(value)

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def get(self, model, identity, **_kwargs):
        return self.sync.get(model, identity)

    def get_bind(self):
        return self.sync.get_bind()

    async def flush(self):
        for value in list(self.sync.new):
            if not hasattr(value, "id") or value.id is not None:
                continue
            table = value.__table__.name
            highest = self.sequences.get(table)
            if highest is None:
                highest = int(self.sync.scalar(select(func.max(value.__table__.c.id))) or 0)
            highest += 1
            self.sequences[table] = highest
            value.id = highest
        self.sync.flush()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


def account(identifier: int) -> Account:
    return Account(
        id=identifier,
        account_type=AccountType.BUSINESS,
        login=f"business_{identifier}",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def profile(identifier: int) -> BusinessProfile:
    return BusinessProfile(
        account_id=identifier,
        name=f"Biznes {identifier}",
        phone="",
        description="",
        public_username=f"cash_{identifier}",
        direction="Savdo",
        activity_type="",
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
    )


def catalog(identifier: int, business_id: int, name: str) -> CatalogItem:
    return CatalogItem(
        id=identifier,
        business_account_id=business_id,
        source_record_key=str(identifier),
        catalog_group_id=None,
        owner_name_snapshot=f"Biznes {business_id}",
        name=name,
        price_text="300 so'm",
        unit="dona",
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
    )


@pytest.fixture
def cash_context():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            BusinessProfile.__table__,
            StaffMember.__table__,
            Debtor.__table__,
            CatalogGroup.__table__,
            CatalogItem.__table__,
            Listing.__table__,
            Order.__table__,
            OrderItem.__table__,
            InventoryItem.__table__,
            StockMove.__table__,
            StockBatch.__table__,
            StockBatchConsumption.__table__,
            CashReceiptCounter.__table__,
            CashReceipt.__table__,
            CashReceiptLine.__table__,
            DebtTransaction.__table__,
        ),
    )
    with Session(engine, expire_on_commit=False) as seed:
        seed.add_all((
            account(1),
            account(2),
            profile(1),
            profile(2),
            Debtor(
                id=501,
                business_account_id=1,
                legacy_source_id=41,
                name="Ali Valiyev",
                phone="+998901234567",
                note="",
                due="",
                created_by_staff_id=None,
                created_at=NOW,
                updated_at=NOW,
            ),
            Debtor(
                id=502,
                business_account_id=2,
                legacy_source_id=42,
                name="Begona qarzdor",
                phone="",
                note="",
                due="",
                created_by_staff_id=None,
                created_at=NOW,
                updated_at=NOW,
            ),
            catalog(11, 1, "Olma"),
            catalog(21, 2, "Begona mahsulot"),
            InventoryItem(
                id=101,
                business_account_id=1,
                catalog_item_id=11,
                legacy_source_id=11,
                track_stock=True,
                stock_type="ready_food",
                stock_qty=Decimal("5"),
                cost_price=100,
                min_qty=Decimal("1"),
                fifo_initialized=True,
                created_at=NOW,
                updated_at=NOW,
            ),
            InventoryItem(
                id=201,
                business_account_id=2,
                catalog_item_id=21,
                legacy_source_id=21,
                track_stock=True,
                stock_type="ready_food",
                stock_qty=Decimal("9"),
                cost_price=50,
                min_qty=Decimal("1"),
                fifo_initialized=True,
                created_at=NOW,
                updated_at=NOW,
            ),
            StockBatch(
                id=1001,
                business_account_id=1,
                inventory_item_id=101,
                legacy_source_id=None,
                qty_in=Decimal("5"),
                qty_remaining=Decimal("5"),
                unit_cost=100,
                source_move_id=None,
                created_at=NOW,
            ),
        ))
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    inventory = InventoryService(sessions, now_provider=lambda: NOW)
    debts = DebtLedgerService(sessions, now_provider=lambda: NOW)
    service = CashRegisterService(
        sessions,
        inventory_service=inventory,
        debt_ledger_service=debts,
        now_provider=lambda: NOW,
    )
    try:
        yield service, debts, engine, sessions
    finally:
        engine.dispose()


def receipt_body(*, qty: float = 2, pay_type: str = "naqd") -> CashReceiptCreate:
    return CashReceiptCreate(
        items=[
            CashSaleLineCreate(catalog_item_id=11, qty=qty, price=300),
            CashSaleLineCreate(name="Paket", qty=1, price=50),
        ],
        pay_type=pay_type,
        note="Sinov",
    )


async def test_multi_line_receipt_updates_fifo_and_daily_totals(cash_context):
    service, _debts, engine, _sessions = cash_context
    created = await service.create_receipt(
        business_account_id=1,
        actor_staff_id=None,
        actor_name="Rahbar",
        permissions=None,
        body=receipt_body(),
    )

    assert created.receipt_no == 1
    assert created.count == 2
    assert created.total == 650
    register = await service.list_receipts(
        business_account_id=1,
        permissions=None,
        day=date(2026, 8, 4),
    )
    assert register.totals.all == 650
    assert register.totals.cash_in == 650
    assert register.totals.naqd == 650
    assert register.receipts[0].lines[0].cost_total == 200

    with Session(engine) as session:
        item = session.get(InventoryItem, 101)
        batch = session.get(StockBatch, 1001)
        assert item is not None and item.stock_qty == Decimal("3.000")
        assert batch is not None and batch.qty_remaining == Decimal("3.000")
        assert session.scalar(select(func.count(StockMove.id))) == 1


async def test_insufficient_fifo_rolls_back_whole_receipt(cash_context):
    service, _debts, engine, _sessions = cash_context
    with pytest.raises(ApiError) as error:
        await service.create_receipt(
            business_account_id=1,
            actor_staff_id=None,
            actor_name="",
            permissions=None,
            body=receipt_body(qty=6),
        )
    assert error.value.code == "inventory_fifo_insufficient"

    with Session(engine) as session:
        assert session.scalar(select(func.count(CashReceipt.id))) == 0
        assert session.get(InventoryItem, 101).stock_qty == Decimal("5.000")
        assert session.get(StockBatch, 1001).qty_remaining == Decimal("5.000")


async def test_delete_receipt_restores_exact_fifo_and_adds_correction(cash_context):
    service, _debts, engine, _sessions = cash_context
    created = await service.create_receipt(
        business_account_id=1,
        actor_staff_id=None,
        actor_name="",
        permissions=None,
        body=receipt_body(),
    )
    await service.delete_receipt(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        receipt_id=created.id,
    )

    with Session(engine) as session:
        assert session.get(CashReceipt, created.id) is None
        assert session.get(InventoryItem, 101).stock_qty == Decimal("5.000")
        assert session.get(StockBatch, 1001).qty_remaining == Decimal("5.000")
        moves = list(session.scalars(select(StockMove).order_by(StockMove.id)))
        assert [move.delta for move in moves] == [Decimal("-2.000"), Decimal("2.000")]
        assert moves[-1].reason == "tuzatish"


async def test_delete_receipt_rolls_back_when_fifo_link_is_missing(cash_context):
    service, _debts, engine, _sessions = cash_context
    created = await service.create_receipt(
        business_account_id=1,
        actor_staff_id=None,
        actor_name="",
        permissions=None,
        body=receipt_body(),
    )
    with Session(engine) as session:
        consumptions = list(session.scalars(select(StockBatchConsumption)))
        for consumption in consumptions:
            session.delete(consumption)
        session.commit()

    with pytest.raises(ApiError) as error:
        await service.delete_receipt(
            business_account_id=1,
            actor_staff_id=None,
            permissions=None,
            receipt_id=created.id,
        )
    assert error.value.code == "inventory_cash_restore_incomplete"

    with Session(engine) as session:
        assert session.get(CashReceipt, created.id) is not None
        assert session.get(InventoryItem, 101).stock_qty == Decimal("3.000")
        assert session.get(StockBatch, 1001).qty_remaining == Decimal("3.000")


async def test_business_scope_permissions_dates_and_debt_guard(cash_context):
    service, _debts, _engine, _sessions = cash_context
    with pytest.raises(ApiError) as foreign:
        await service.create_receipt(
            business_account_id=1,
            actor_staff_id=None,
            actor_name="",
            permissions=None,
            body=CashReceiptCreate(items=[
                CashSaleLineCreate(catalog_item_id=21, qty=1, price=100),
            ]),
        )
    assert foreign.value.code == "cash_catalog_item_not_found"

    with pytest.raises(ApiError) as permission:
        await service.catalog(business_account_id=1, permissions=("ombor",))
    assert permission.value.code == "staff_permission_required"

    with pytest.raises(ApiError) as future:
        await service.create_receipt(
            business_account_id=1,
            actor_staff_id=None,
            actor_name="",
            permissions=None,
            body=receipt_body().model_copy(update={"sale_date": date(2026, 8, 5)}),
        )
    assert future.value.code == "cash_future_date_forbidden"

    with pytest.raises(ApiError) as debt:
        await service.create_receipt(
            business_account_id=1,
            actor_staff_id=None,
            actor_name="",
            permissions=None,
            body=receipt_body(pay_type="qarz"),
        )
    assert debt.value.code == "debt_debtor_required"

    with pytest.raises(ApiError) as foreign_debtor:
        await service.create_receipt(
            business_account_id=1,
            actor_staff_id=None,
            actor_name="",
            permissions=None,
            body=receipt_body(pay_type="qarz").model_copy(
                update={"debtor_id": 502}
            ),
        )
    assert foreign_debtor.value.code == "debt_debtor_required"


async def test_debt_receipt_and_payment_share_atomic_cash_ledger(cash_context):
    service, debts, engine, _sessions = cash_context
    created = await service.create_receipt(
        business_account_id=1,
        actor_staff_id=None,
        actor_name="Rahbar",
        permissions=None,
        body=receipt_body(pay_type="qarz").model_copy(
            update={"debtor_id": 501}
        ),
    )

    detail = await debts.get_debtor(
        business_account_id=1,
        permissions=None,
        debtor_id=501,
    )
    assert detail.balance == 650
    assert [row.amount for row in detail.tx] == [600, 50]

    paid = await debts.add_transaction(
        business_account_id=1,
        actor_staff_id=None,
        actor_name="Rahbar",
        permissions=None,
        debtor_id=501,
        body=DebtTransactionCreate(type="payment", amount=250, note="Qisman"),
    )
    assert paid.balance == 400
    register = await service.list_receipts(
        business_account_id=1,
        permissions=None,
        day=date(2026, 8, 4),
    )
    assert register.totals.all == 900
    assert register.totals.qarz == 650
    assert register.totals.qarzpay == 250
    assert register.totals.cash_in == 250
    payment_receipt = next(
        row for row in register.receipts if row.source == "debt_payment"
    )
    assert payment_receipt.debtor_name == "Ali Valiyev"

    await service.delete_receipt(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        receipt_id=payment_receipt.id,
    )
    assert (await debts.get_debtor(
        business_account_id=1,
        permissions=None,
        debtor_id=501,
    )).balance == 650

    await service.delete_receipt(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        receipt_id=created.id,
    )
    assert (await debts.get_debtor(
        business_account_id=1,
        permissions=None,
        debtor_id=501,
    )).balance == 0
    with Session(engine) as session:
        assert session.scalar(select(func.count(DebtTransaction.id))) == 0
        assert session.get(InventoryItem, 101).stock_qty == Decimal("5.000")


async def test_backdated_debt_sale_and_payment_keep_the_selected_day(cash_context):
    service, debts, _engine, _sessions = cash_context
    selected_day = date(2026, 8, 2)
    await service.create_receipt(
        business_account_id=1,
        actor_staff_id=None,
        actor_name="Rahbar",
        permissions=None,
        body=receipt_body(pay_type="qarz").model_copy(update={
            "debtor_id": 501,
            "sale_date": selected_day,
        }),
    )
    await debts.add_transaction(
        business_account_id=1,
        actor_staff_id=None,
        actor_name="Rahbar",
        permissions=None,
        debtor_id=501,
        body=DebtTransactionCreate(
            type="payment",
            amount=100,
            date=selected_day,
            note="Eski kundagi to‘lov",
        ),
    )

    detail = await debts.get_debtor(
        business_account_id=1,
        permissions=None,
        debtor_id=501,
    )
    assert {row.date for row in detail.tx} == {selected_day}
    register = await service.list_receipts(
        business_account_id=1,
        permissions=None,
        day=selected_day,
    )
    assert register.totals.qarz == 650
    assert register.totals.qarzpay == 100


async def test_debt_ledger_permissions_initial_balance_and_future_guard(cash_context):
    _service, debts, _engine, _sessions = cash_context
    created = await debts.create_debtor(
        business_account_id=1,
        actor_staff_id=None,
        permissions=("kassa",),
        body=DebtorCreate(
            name="Vali Karimov",
            phone="+998909999999",
            initial_debt=75_000,
        ),
    )
    rows = await debts.list_debtors(
        business_account_id=1,
        permissions=("kassa",),
    )
    assert next(row for row in rows if row.id == created.id).balance == 75_000

    with pytest.raises(ApiError) as permission:
        await debts.get_debtor(
            business_account_id=1,
            permissions=("kassa",),
            debtor_id=created.id,
        )
    assert permission.value.code == "staff_permission_required"

    with pytest.raises(ApiError) as future:
        await debts.add_transaction(
            business_account_id=1,
            actor_staff_id=None,
            actor_name="Rahbar",
            permissions=None,
            debtor_id=created.id,
            body=DebtTransactionCreate(
                type="debt",
                amount=1,
                date=date(2026, 8, 5),
            ),
        )
    assert future.value.code == "debt_future_date_forbidden"


async def test_order_posting_is_idempotent_and_debt_payment_is_reversible(
    cash_context,
):
    service, _debts, engine, sessions = cash_context
    with Session(engine, expire_on_commit=False) as seed:
        order = Order(
            id=301,
            legacy_source_id=901,
            customer_account_id=2,
            customer_kind="business",
            customer_name="Mijoz",
            customer_phone="",
            provider_account_id=1,
            provider_kind="business",
            provider_name="Biznes 1",
            provider_phone="",
            item_id=11,
            listing_id=None,
            title="Olma",
            note="",
            phone="",
            order_type="pickup",
            order_category="product",
            address="",
            desired_time="",
            delivery_lat=None,
            delivery_lng=None,
            qty=Decimal("2"),
            total_amount=600,
            status="tayyor",
            payment_status="confirmed",
            pay_type="karta",
            receipt_message_id=None,
            problem_open=False,
            problem_reason="",
            problem_note="",
            problem_solution="",
            problem_opened_at=None,
            problem_resolved_at=None,
            last_event="tayyor",
            customer_seen_at=NOW,
            provider_seen_at=NOW,
            accepted_at=NOW,
            ready_at=NOW,
            handed_off_at=None,
            seller_completed_at=None,
            customer_received_at=None,
            created_at=NOW,
            updated_at=NOW,
        )
        seed.add(order)
        seed.add(OrderItem(
            id=401,
            order_id=301,
            legacy_source_id=902,
            catalog_item_id=11,
            item_name="Olma",
            price_text="300 so'm",
            qty=Decimal("2"),
            unit="dona",
            line_total=600,
            note="",
            kind="product",
            created_at=NOW,
        ))
        seed.commit()

    async with sessions() as session:
        order = await session.get(Order, 301)
        first = await service.post_order(
            session, order=order, actor_staff_id=None
        )
        second = await service.post_order(
            session, order=order, actor_staff_id=None
        )
        await session.commit()
        assert first is not None and second is not None and first.id == second.id

    with Session(engine) as session:
        assert session.scalar(select(func.count(CashReceipt.id))) == 1
        receipt = session.scalar(select(CashReceipt))
        assert receipt is not None and receipt.source == "order"
        assert receipt.pay_type == "karta"
        receipt_id = receipt.id
        assert session.get(InventoryItem, 101).stock_qty == Decimal("3.000")

    updated = await service.update_order_payment(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        receipt_id=receipt_id,
        body=CashPaymentUpdate(pay_type="qarz", debtor_id=501),
    )
    assert updated.pay_type == "qarz"
    assert (await _debts.get_debtor(
        business_account_id=1,
        permissions=None,
        debtor_id=501,
    )).balance == 600

    updated = await service.update_order_payment(
        business_account_id=1,
        actor_staff_id=None,
        permissions=None,
        receipt_id=receipt_id,
        body=CashPaymentUpdate(pay_type="karta"),
    )
    assert updated.pay_type == "karta"
    assert (await _debts.get_debtor(
        business_account_id=1,
        permissions=None,
        debtor_id=501,
    )).balance == 0


async def test_postgresql_receipt_counter_is_atomic():
    captured = []

    class Bind:
        dialect = postgresql.dialect()

    class SessionCapture:
        def get_bind(self):
            return Bind()

        async def scalar(self, statement):
            captured.append(statement)
            return 9

    value = await CashRegisterRepository().next_receipt_no(
        SessionCapture(),
        business_account_id=1,
        now=NOW,
    )
    sql = str(captured[0].compile(dialect=postgresql.dialect())).upper()
    assert value == 9
    assert "ON CONFLICT" in sql
    assert "RETURNING CASH_RECEIPT_COUNTERS.LAST_RECEIPT_NO" in sql


async def test_cash_inventory_locks_are_deduplicated_and_ordered():
    calls = []

    class RepositoryCapture:
        async def inventory_item_by_catalog(self, _session, **kwargs):
            calls.append(kwargs)
            return None

    inventory = InventoryService(
        lambda: None,
        repository=RepositoryCapture(),
        now_provider=lambda: NOW,
    )
    await inventory.lock_cash_catalog_items(
        object(),
        business_account_id=7,
        catalog_item_ids=[11, 4, 11, 9],
    )

    assert [call["catalog_item_id"] for call in calls] == [4, 9, 11]
    assert all(call["business_account_id"] == 7 for call in calls)
    assert all(call["lock"] is True for call in calls)
