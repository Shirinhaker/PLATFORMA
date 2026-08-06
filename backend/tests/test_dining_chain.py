"""Ovqatlanish zanjiri: ofitsiant → oshpaz → kassa → ombor.

Bu testlar migratsiyagacha bo'lgan uzilishni qaytadan yuzaga kelishidan
saqlaydi: `kitchen_status` hech qachon `done`, `payment_status` hech
qachon `confirmed` bo'lmagani uchun stol abadiy band qolardi.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.cash_register.model import (
    CashReceipt,
    CashReceiptCounter,
    CashReceiptLine,
)
from app.catalog.model import CatalogGroup, CatalogItem
from app.core.errors import ApiError
from app.db.base import Base
from app.debt_ledger.model import Debtor, DebtTransaction
from app.debt_ledger.service import DebtLedgerService
from app.dining.model import DiningOrder, DiningOrderItem, DiningPlace
from app.dining.schemas import (
    DiningCancel,
    DiningCashierItemsUpdate,
    DiningCashierLine,
    DiningItemInput,
    DiningItemsAdd,
    DiningKitchenUpdate,
    DiningOrderCreate,
    DiningPaymentCreate,
    DiningProblemOpen,
)
from app.dining.service import DiningService
from app.inventory.model import (
    InventoryItem,
    StockBatch,
    StockBatchConsumption,
    StockMove,
)
from app.inventory.service import InventoryService
from app.legacy_migration.model import OwnerState, ReviewState
from app.listings.model import Listing
from app.notifications.model import Notification
from app.orders.model import Order, OrderItem
from app.profiles.model import BusinessProfile
from app.staff.model import StaffMember


NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)

BUSINESS = 1
PLACE = 700
# "Osh" — 12 000 so'm, omborda 10 dona, FIFO tannarxi 4 000.
OSH = 11
# "Non" — 2 000 so'm, omborda hisob yuritilmaydi.
NON = 12
# Ofitsiant Dilnoza.
WAITER = 300


class AsyncStore:
    """Sinxron `Session` ustidan async interfeys — tests uchun."""

    def __init__(self, sync: Session) -> None:
        self.sync = sync
        self.sequences: dict[str, int] = {}

    def add(self, value):
        self.sync.add(value)

    def add_all(self, values):
        self.sync.add_all(values)

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
                highest = int(
                    self.sync.scalar(select(func.max(value.__table__.c.id))) or 0
                )
            highest += 1
            self.sequences[table] = highest
            value.id = highest
        self.sync.flush()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


def _catalog(identifier: int, name: str, price: str) -> CatalogItem:
    return CatalogItem(
        id=identifier,
        business_account_id=BUSINESS,
        source_record_key=str(identifier),
        catalog_group_id=None,
        owner_name_snapshot="Choyxona",
        name=name,
        price_text=price,
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
def dining_context():
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
            # `cash_receipts` tashqi buyurtmaga havola qiladi.
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
            Notification.__table__,
            DiningPlace.__table__,
            DiningOrder.__table__,
            DiningOrderItem.__table__,
        ),
    )
    with Session(engine, expire_on_commit=False) as seed:
        seed.add_all((
            Account(
                id=BUSINESS,
                account_type=AccountType.BUSINESS,
                login="choyxona",
                password_hash="hash",
                telegram_user_id=None,
                status="active",
                created_at=NOW,
                updated_at=NOW,
            ),
            StaffMember(
                id=WAITER,
                business_account_id=BUSINESS,
                legacy_source_id=None,
                name="Dilnoza",
                profession="Ofitsiant",
                phone="",
                salary=0,
                hire_date=None,
                status="active",
                note="",
                login=None,
                password_hash=None,
                can_login=True,
                permissions=["dining_places", "dining_internal"],
                schedule={},
                created_at=NOW,
                updated_at=NOW,
            ),
            Debtor(
                id=901,
                business_account_id=BUSINESS,
                legacy_source_id=None,
                name="Anvar aka",
                phone="+998901112233",
                note="",
                due="",
                created_by_staff_id=None,
                created_at=NOW,
                updated_at=NOW,
            ),
            _catalog(OSH, "Osh", "12000 so'm"),
            _catalog(NON, "Non", "2000 so'm"),
            InventoryItem(
                id=101,
                business_account_id=BUSINESS,
                catalog_item_id=OSH,
                legacy_source_id=None,
                track_stock=True,
                stock_type="ready_food",
                stock_qty=Decimal("10"),
                cost_price=4000,
                min_qty=Decimal("0"),
                fifo_initialized=True,
                created_at=NOW,
                updated_at=NOW,
            ),
            StockBatch(
                id=1001,
                business_account_id=BUSINESS,
                inventory_item_id=101,
                legacy_source_id=None,
                qty_in=Decimal("10"),
                qty_remaining=Decimal("10"),
                unit_cost=4000,
                source_move_id=None,
                created_at=NOW,
            ),
            DiningPlace(
                id=PLACE,
                business_account_id=BUSINESS,
                legacy_source_id=None,
                kind="table",
                name="1-stol",
                seats=4,
                x=4,
                y=4,
                locked=True,
                created_at=NOW,
                updated_at=NOW,
            ),
        ))
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    inventory = InventoryService(sessions, now_provider=lambda: NOW)
    debts = DebtLedgerService(sessions, now_provider=lambda: NOW)
    service = DiningService(
        sessions,
        inventory=inventory,
        debt_ledger=debts,
        now_provider=lambda: NOW,
    )
    try:
        yield service, engine
    finally:
        engine.dispose()


async def _open_order(service: DiningService, *, qty: int = 2):
    return await service.create_order(
        business_account_id=BUSINESS,
        permissions=None,
        place_id=PLACE,
        actor_staff_id=WAITER,
        body=DiningOrderCreate(
            items=[DiningItemInput(item_id=OSH, qty=Decimal(qty))],
            customer_name="Mehmon",
            note="",
        ),
    )


# --------------------------------------------------------------- to'liq zanjir


async def test_full_chain_frees_the_table(dining_context):
    """Zakaz → oshpaz → kassa → yakunlash → stol bo'shaydi."""
    service, engine = dining_context

    order = await _open_order(service)
    assert order.kitchen_status == "preparing"
    assert order.payment_status == "open"
    assert order.total == 24000

    await service.set_kitchen_status(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        body=DiningKitchenUpdate(status="done"),
    )
    paid = await service.confirm_payment(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        actor_staff_id=None,
        body=DiningPaymentCreate(pay_type="naqd"),
    )
    assert paid.receipt_no == 1

    finalized = await service.finalize(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
    )
    assert finalized.status == "done"

    # Stol endi bo'sh — zal rejasida band ko'rinmaydi.
    places = await service.list_places(
        business_account_id=BUSINESS, permissions=None
    )
    assert [place.occupied for place in places] == [False]
    with Session(engine) as check:
        stored = check.get(DiningOrder, order.id)
        assert stored.status == "done"
        assert stored.kitchen_status == "done"
        assert stored.payment_status == "confirmed"


async def test_table_cannot_be_cleared_before_kitchen_and_payment(dining_context):
    """Migratsiyagacha bo'lgan tiqilish qaytmasligi uchun.

    Ilgari `kitchen`/`payment` endpointlari yo'q edi, shuning uchun bu
    409 abadiy qolardi. Endi ikkala qadam bajarilgach, stol bo'shaydi.
    """
    service, _engine = dining_context
    order = await _open_order(service)

    with pytest.raises(ApiError) as blocked:
        await service.clear_place(
            business_account_id=BUSINESS, permissions=None, place_id=PLACE
        )
    assert blocked.value.status_code == 409
    assert blocked.value.code == "dining_place_has_unfinished_order"

    # Faqat oshxona bajarilsa ham hali yetarli emas.
    await service.set_kitchen_status(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        body=DiningKitchenUpdate(status="done"),
    )
    with pytest.raises(ApiError) as still_blocked:
        await service.clear_place(
            business_account_id=BUSINESS, permissions=None, place_id=PLACE
        )
    assert still_blocked.value.status_code == 409

    await service.confirm_payment(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        actor_staff_id=None,
        body=DiningPaymentCreate(pay_type="karta"),
    )
    await service.clear_place(
        business_account_id=BUSINESS, permissions=None, place_id=PLACE
    )
    places = await service.list_places(
        business_account_id=BUSINESS, permissions=None
    )
    assert places[0].occupied is False


# ------------------------------------------------------------ ombor va kassa


async def test_payment_consumes_stock_and_writes_receipt(dining_context):
    service, engine = dining_context
    order = await _open_order(service, qty=3)

    await service.confirm_payment(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        actor_staff_id=None,
        body=DiningPaymentCreate(pay_type="naqd"),
    )

    with Session(engine) as check:
        item = check.get(InventoryItem, 101)
        assert item.stock_qty == Decimal("7.000")

        move = check.scalar(select(StockMove).where(StockMove.reason == "sotuv"))
        assert move is not None
        assert move.delta == Decimal("-3.000")
        assert move.note == f"Ichki buyurtma #{order.id}"

        receipt = check.scalar(select(CashReceipt))
        assert receipt.source == "dining"
        assert receipt.receipt_no == 1
        assert receipt.pay_type == "naqd"
        assert receipt.waiter_name_snapshot == "Dilnoza"

        line = check.scalar(select(CashReceiptLine))
        assert line.item_name == "Osh"
        assert line.total == 36000
        # FIFO tannarxi: 3 × 4 000.
        assert line.cost_total == 12000

        stored = check.get(DiningOrder, order.id)
        assert stored.cash_receipt_id == receipt.id


async def test_untracked_item_does_not_touch_warehouse(dining_context):
    """Omborda yozuvi yo'q taom ham sotiladi — chekda qoladi, sarf yo'q."""
    service, engine = dining_context
    order = await service.create_order(
        business_account_id=BUSINESS,
        permissions=None,
        place_id=PLACE,
        actor_staff_id=WAITER,
        body=DiningOrderCreate(
            items=[DiningItemInput(item_id=NON, qty=Decimal(4))],
            customer_name="",
            note="",
        ),
    )
    assert order.total == 8000

    await service.confirm_payment(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        actor_staff_id=None,
        body=DiningPaymentCreate(pay_type="naqd"),
    )
    with Session(engine) as check:
        assert check.scalar(select(func.count()).select_from(StockMove)) == 0
        line = check.scalar(select(CashReceiptLine))
        assert line.item_name == "Non"
        assert line.cost_total == 0


async def test_debt_payment_writes_debt_transaction(dining_context):
    service, engine = dining_context
    order = await _open_order(service)

    await service.confirm_payment(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        actor_staff_id=None,
        body=DiningPaymentCreate(pay_type="qarz", debtor_id=901),
    )

    with Session(engine) as check:
        transaction = check.scalar(select(DebtTransaction))
        assert transaction.transaction_type == "debt"
        assert transaction.amount == 24000
        assert transaction.debtor_id == 901

        receipt = check.scalar(select(CashReceipt))
        assert receipt.debtor_id == 901
        assert receipt.debtor_name_snapshot == "Anvar aka"

        stored = check.get(DiningOrder, order.id)
        assert stored.debtor_id == 901


async def test_debt_payment_requires_debtor(dining_context):
    service, engine = dining_context
    order = await _open_order(service)

    with pytest.raises(ApiError) as failure:
        await service.confirm_payment(
            business_account_id=BUSINESS,
            permissions=None,
            order_id=order.id,
            actor_staff_id=None,
            body=DiningPaymentCreate(pay_type="qarz"),
        )
    assert failure.value.status_code == 400

    # Chek yozilib qolmagan bo'lishi kerak.
    with Session(engine) as check:
        assert check.scalar(select(func.count()).select_from(CashReceipt)) == 0


async def test_payment_is_idempotent(dining_context):
    service, engine = dining_context
    order = await _open_order(service)

    first = await service.confirm_payment(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        actor_staff_id=None,
        body=DiningPaymentCreate(pay_type="naqd"),
    )
    second = await service.confirm_payment(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        actor_staff_id=None,
        body=DiningPaymentCreate(pay_type="naqd"),
    )
    assert second.already_confirmed is True
    assert second.receipt_no == first.receipt_no
    with Session(engine) as check:
        assert check.scalar(select(func.count()).select_from(CashReceipt)) == 1
        assert check.scalar(select(InventoryItem.stock_qty).where(
            InventoryItem.id == 101
        )) == Decimal("8.000")


# ---------------------------------------------------------------- kassir ishi


async def test_cashier_edits_and_deletes_lines(dining_context):
    service, engine = dining_context
    order = await service.create_order(
        business_account_id=BUSINESS,
        permissions=None,
        place_id=PLACE,
        actor_staff_id=WAITER,
        body=DiningOrderCreate(
            items=[
                DiningItemInput(item_id=OSH, qty=Decimal(2)),
                DiningItemInput(item_id=NON, qty=Decimal(2)),
            ],
            customer_name="",
            note="",
        ),
    )
    assert order.total == 28000
    osh_line = next(line for line in order.items if line.name == "Osh")
    non_line = next(line for line in order.items if line.name == "Non")

    updated = await service.update_cashier_items(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        body=DiningCashierItemsUpdate(items=[
            DiningCashierLine(line_id=osh_line.id, qty=Decimal(1)),
            DiningCashierLine(line_id=non_line.id, qty=Decimal(0)),
        ]),
    )
    assert updated.total == 12000
    assert [line.name for line in updated.items] == ["Osh"]
    with Session(engine) as check:
        assert check.scalar(
            select(func.count()).select_from(DiningOrderItem)
        ) == 1


async def test_cashier_cannot_empty_the_bill(dining_context):
    service, engine = dining_context
    order = await _open_order(service)
    line = order.items[0]

    with pytest.raises(ApiError) as failure:
        await service.update_cashier_items(
            business_account_id=BUSINESS,
            permissions=None,
            order_id=order.id,
            body=DiningCashierItemsUpdate(items=[
                DiningCashierLine(line_id=line.id, qty=Decimal(0)),
            ]),
        )
    assert failure.value.status_code == 400
    assert failure.value.code == "dining_order_empty"

    # Rollback qatorni qaytargan bo'lishi kerak.
    with Session(engine) as check:
        assert check.scalar(
            select(func.count()).select_from(DiningOrderItem)
        ) == 1
        assert check.get(DiningOrder, order.id).total == 24000


async def test_paid_bill_cannot_be_edited_or_cancelled(dining_context):
    service, _engine = dining_context
    order = await _open_order(service)
    await service.confirm_payment(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        actor_staff_id=None,
        body=DiningPaymentCreate(pay_type="naqd"),
    )

    with pytest.raises(ApiError) as cancelled:
        await service.cancel(
            business_account_id=BUSINESS,
            permissions=None,
            order_id=order.id,
            body=DiningCancel(reason="Mijoz voz kechdi"),
        )
    assert cancelled.value.status_code == 409

    with pytest.raises(ApiError) as added:
        await service.add_items(
            business_account_id=BUSINESS,
            permissions=None,
            order_id=order.id,
            body=DiningItemsAdd(items=[
                DiningItemInput(item_id=NON, qty=Decimal(1)),
            ]),
        )
    assert added.value.status_code == 400


async def test_cancel_requires_reason_and_frees_the_table(dining_context):
    service, engine = dining_context
    order = await _open_order(service)

    cancelled = await service.cancel(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        body=DiningCancel(reason="Mijoz voz kechdi"),
    )
    assert cancelled.status == "cancelled"
    assert cancelled.problem_note == "Mijoz voz kechdi"

    places = await service.list_places(
        business_account_id=BUSINESS, permissions=None
    )
    assert places[0].occupied is False
    with Session(engine) as check:
        assert check.scalar(select(func.count()).select_from(CashReceipt)) == 0


# ------------------------------------------------------------------- muammo


async def test_problem_blocks_kitchen_and_payment_until_resolved(dining_context):
    service, _engine = dining_context
    order = await _open_order(service)

    await service.open_problem(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        body=DiningProblemOpen(reason="Noto‘g‘ri hisob", note="Ikki marta"),
    )

    with pytest.raises(ApiError) as kitchen:
        await service.set_kitchen_status(
            business_account_id=BUSINESS,
            permissions=None,
            order_id=order.id,
            body=DiningKitchenUpdate(status="done"),
        )
    assert kitchen.value.status_code == 409

    with pytest.raises(ApiError) as payment:
        await service.confirm_payment(
            business_account_id=BUSINESS,
            permissions=None,
            order_id=order.id,
            actor_staff_id=None,
            body=DiningPaymentCreate(pay_type="naqd"),
        )
    assert payment.value.status_code == 409

    resolved = await service.resolve_problem(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
    )
    assert resolved.problem_open is False

    await service.set_kitchen_status(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        body=DiningKitchenUpdate(status="done"),
    )


async def test_finalize_requires_payment_and_kitchen(dining_context):
    service, _engine = dining_context
    order = await _open_order(service)

    with pytest.raises(ApiError) as unpaid:
        await service.finalize(
            business_account_id=BUSINESS, permissions=None, order_id=order.id
        )
    assert unpaid.value.code == "dining_payment_required"

    await service.confirm_payment(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        actor_staff_id=None,
        body=DiningPaymentCreate(pay_type="naqd"),
    )
    with pytest.raises(ApiError) as raw:
        await service.finalize(
            business_account_id=BUSINESS, permissions=None, order_id=order.id
        )
    assert raw.value.code == "dining_kitchen_pending"


# ------------------------------------------------------------------ vakolat


@pytest.mark.parametrize(
    ("permissions", "allowed"),
    [
        (("kitchen",), True),
        (("kassa",), False),
        (("dining_internal",), False),
    ],
)
async def test_only_kitchen_staff_marks_food_ready(
    dining_context, permissions, allowed
):
    service, _engine = dining_context
    order = await _open_order(service)

    async def act():
        return await service.set_kitchen_status(
            business_account_id=BUSINESS,
            permissions=permissions,
            order_id=order.id,
            body=DiningKitchenUpdate(status="done"),
        )

    if allowed:
        assert (await act()).kitchen_status == "done"
        return
    with pytest.raises(ApiError) as failure:
        await act()
    assert failure.value.status_code == 403


@pytest.mark.parametrize(
    ("permissions", "allowed"),
    [
        (("kassa",), True),
        (("payment_confirm",), True),
        (("kitchen",), False),
        (("dining_internal",), False),
    ],
)
async def test_only_cashier_confirms_payment(
    dining_context, permissions, allowed
):
    service, _engine = dining_context
    order = await _open_order(service)

    async def act():
        return await service.confirm_payment(
            business_account_id=BUSINESS,
            permissions=permissions,
            order_id=order.id,
            actor_staff_id=None,
            body=DiningPaymentCreate(pay_type="naqd"),
        )

    if allowed:
        assert (await act()).receipt_no == 1
        return
    with pytest.raises(ApiError) as failure:
        await act()
    assert failure.value.status_code == 403


async def test_other_business_cannot_touch_the_order(dining_context):
    service, _engine = dining_context
    order = await _open_order(service)

    with pytest.raises(ApiError) as failure:
        await service.confirm_payment(
            business_account_id=BUSINESS + 5,
            permissions=None,
            order_id=order.id,
            actor_staff_id=None,
            body=DiningPaymentCreate(pay_type="naqd"),
        )
    assert failure.value.status_code == 404


# ------------------------------------------------------------------- narxlar


async def test_price_comes_from_catalog_not_from_client(dining_context):
    """Mijoz narx yubormaydi — server katalogdan oladi."""
    service, _engine = dining_context
    order = await _open_order(service, qty=2)
    assert order.items[0].price == 12000
    assert order.items[0].total == 24000


async def test_waiter_name_comes_from_staff_record(dining_context):
    """Chekdagi ism xodim yozuvidan olinadi, rahbar uchun 'Rahbar'."""
    service, _engine = dining_context
    by_staff = await _open_order(service)
    assert by_staff.waiter_staff_id == WAITER
    assert by_staff.waiter_name == "Dilnoza"

    by_owner = await service.create_order(
        business_account_id=BUSINESS,
        permissions=None,
        place_id=PLACE,
        actor_staff_id=None,
        body=DiningOrderCreate(
            items=[DiningItemInput(item_id=NON, qty=Decimal(1))],
            customer_name="",
            note="",
        ),
    )
    assert by_owner.waiter_staff_id is None
    assert by_owner.waiter_name == "Rahbar"


async def test_adding_items_reopens_the_kitchen(dining_context):
    service, _engine = dining_context
    order = await _open_order(service)
    await service.set_kitchen_status(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        body=DiningKitchenUpdate(status="done"),
    )

    updated = await service.add_items(
        business_account_id=BUSINESS,
        permissions=None,
        order_id=order.id,
        body=DiningItemsAdd(items=[
            DiningItemInput(item_id=NON, qty=Decimal(3)),
        ]),
    )
    assert updated.kitchen_status == "preparing"
    assert updated.total == 30000
