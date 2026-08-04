from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.cash_register.model import CashReceipt, CashReceiptLine
from app.catalog.model import CatalogItem
from app.core.errors import ApiError
from app.db.base import Base
from app.debt_ledger.model import Debtor  # noqa: F401 -- FK metadata target
from app.expenses.model import Expense
from app.inventory.model import InventoryItem, StockMove
from app.legacy_migration.model import OwnerState, ReviewState
from app.orders.model import Order  # noqa: F401 -- FK metadata target
from app.staff.model import StaffMember
from app.statistics.service import StatisticsService


NOW = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)  # Toshkentda 14:00


class AsyncStore:
    def __init__(self, sync: Session) -> None:
        self.sync = sync

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def rollback(self):
        self.sync.rollback()


def account(identifier: int) -> Account:
    return Account(
        id=identifier,
        account_type=AccountType.BUSINESS,
        login=f"stats_business_{identifier}",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def staff(identifier: int, business_id: int, name: str) -> StaffMember:
    return StaffMember(
        id=identifier,
        business_account_id=business_id,
        legacy_source_id=None,
        name=name,
        profession="Kassir",
        phone="",
        salary=0,
        hire_date=None,
        status="active",
        note="",
        login=None,
        password_hash=None,
        can_login=False,
        permissions=[],
        schedule={},
        created_at=NOW,
        updated_at=NOW,
        fired_at=None,
    )


def catalog(identifier: int, business_id: int, name: str) -> CatalogItem:
    return CatalogItem(
        id=identifier,
        business_account_id=business_id,
        source_record_key=str(identifier),
        catalog_group_id=None,
        owner_name_snapshot=f"Biznes {business_id}",
        name=name,
        price_text="",
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


def receipt(
    identifier: int,
    business_id: int,
    *,
    source: str,
    pay_type: str,
    staff_id: int | None,
    actor: str,
    waiter_id: int | None = None,
    waiter_name: str = "",
    created_at: datetime = NOW,
) -> CashReceipt:
    return CashReceipt(
        id=identifier,
        business_account_id=business_id,
        receipt_no=identifier,
        source=source,
        order_id=None,
        legacy_order_source_id=None,
        legacy_group_key=None,
        pay_type=pay_type,
        debtor_id=None,
        debtor_name_snapshot="",
        legacy_debtor_source_id=None,
        note="",
        created_by_staff_id=staff_id,
        actor_name_snapshot=actor,
        waiter_staff_id=waiter_id,
        waiter_name_snapshot=waiter_name,
        created_at=created_at,
    )


def line(
    identifier: int,
    receipt_id: int,
    business_id: int,
    name: str,
    total: int,
    cost: int,
    *,
    qty: str = "1",
    unit: str = "dona",
) -> CashReceiptLine:
    return CashReceiptLine(
        id=identifier,
        receipt_id=receipt_id,
        business_account_id=business_id,
        catalog_item_id=None,
        inventory_item_id=None,
        legacy_source_key=None,
        item_name=name,
        qty=Decimal(qty),
        unit=unit,
        unit_price=total,
        total=total,
        cost_total=cost,
        created_at=NOW,
    )


@pytest.fixture
def statistics_context():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            StaffMember.__table__,
            CatalogItem.__table__,
            InventoryItem.__table__,
            StockMove.__table__,
            CashReceipt.__table__,
            CashReceiptLine.__table__,
            Expense.__table__,
        ),
    )
    with Session(engine) as seed:
        seed.add_all((
            account(1),
            account(2),
            staff(11, 1, "Kassir Ali"),
            staff(12, 1, "Ofitsiant Lola"),
            catalog(101, 1, "Olma"),
            catalog(102, 1, "Paket"),
            catalog(201, 2, "Begona tovar"),
            InventoryItem(
                id=1001,
                business_account_id=1,
                catalog_item_id=101,
                legacy_source_id=None,
                track_stock=True,
                stock_type="ready_food",
                stock_qty=Decimal("3"),
                cost_price=100,
                min_qty=Decimal("5"),
                fifo_initialized=True,
                created_at=NOW,
                updated_at=NOW,
            ),
            InventoryItem(
                id=1002,
                business_account_id=1,
                catalog_item_id=102,
                legacy_source_id=None,
                track_stock=True,
                stock_type="ready_food",
                stock_qty=Decimal("8"),
                cost_price=0,
                min_qty=Decimal("1"),
                fifo_initialized=True,
                created_at=NOW,
                updated_at=NOW,
            ),
            InventoryItem(
                id=2001,
                business_account_id=2,
                catalog_item_id=201,
                legacy_source_id=None,
                track_stock=True,
                stock_type="ready_food",
                stock_qty=Decimal("-9"),
                cost_price=1,
                min_qty=Decimal("5"),
                fifo_initialized=True,
                created_at=NOW,
                updated_at=NOW,
            ),
            receipt(1, 1, source="manual", pay_type="naqd", staff_id=11, actor=""),
            receipt(2, 1, source="order", pay_type="karta", staff_id=None, actor="Rahbar"),
            receipt(
                3,
                1,
                source="dining",
                pay_type="qarz",
                staff_id=11,
                actor="",
                waiter_id=12,
            ),
            receipt(4, 1, source="debt_payment", pay_type="naqd", staff_id=None, actor="Rahbar"),
            receipt(5, 2, source="manual", pay_type="naqd", staff_id=None, actor="Begona"),
            line(1, 1, 1, "Olma", 600, 200, qty="2"),
            line(2, 1, 1, "Paket", 50, 0),
            line(3, 2, 1, "Olma", 400, 100),
            line(4, 3, 1, "Osh", 300, 120),
            line(5, 4, 1, "Qarz to‘lovi", 200, 0),
            line(6, 5, 2, "Begona tovar", 999_999, 1),
            Expense(
                id=1,
                business_account_id=1,
                legacy_source_id=None,
                category="Ijara",
                amount=75,
                note="",
                source="manual",
                inventory_stock_move_id=None,
                performed_by_staff_id=None,
                actor_name_snapshot="",
                created_at=NOW,
            ),
            Expense(
                id=2,
                business_account_id=1,
                legacy_source_id=None,
                category="Tovar xaridi",
                amount=200,
                note="",
                source="stock",
                inventory_stock_move_id=None,
                performed_by_staff_id=None,
                actor_name_snapshot="",
                created_at=NOW,
            ),
            Expense(
                id=3,
                business_account_id=2,
                legacy_source_id=None,
                category="Ijara",
                amount=700_000,
                note="",
                source="manual",
                inventory_stock_move_id=None,
                performed_by_staff_id=None,
                actor_name_snapshot="",
                created_at=NOW,
            ),
        ))
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    try:
        yield StatisticsService(sessions, now_provider=lambda: NOW), engine
    finally:
        engine.dispose()


async def test_report_matches_v1656_financial_and_activity_formulas(statistics_context):
    service, _engine = statistics_context

    report = await service.report(
        business_account_id=1,
        permissions=None,
        period="kun",
        anchor="2026-08-04",
    )

    assert report.label == "2026-08-04"
    assert report.revenue == 1_350
    assert report.cash_in == 1_250
    assert report.cogs == 420
    assert report.gross_profit == 930
    assert report.expenses == 75
    assert report.inventory_purchases == 200
    assert report.profit == 855
    assert report.qarzpay == 200
    assert report.pay.model_dump() == {
        "naqd": 650,
        "karta": 400,
        "qarz": 300,
        "order": 0,
    }
    assert report.source_split.model_dump() == {
        "internal": {"count": 1, "total": 300},
        "external": {"count": 1, "total": 400},
        "manual": {"count": 2, "total": 650},
    }
    assert report.sales_count == 4
    assert report.exp_by_cat == {"Ijara": 75, "Tovar xaridi": 200}

    hour = next(point for point in report.trend if point.label == "14")
    assert hour.model_dump() == {
        "label": "14", "rev": 1_350, "exp": 75,
        "cogs": 420, "profit": 855,
    }
    assert report.top_products[0].model_dump() == {
        "name": "Olma", "qty": 3.0, "unit": "dona",
        "total": 1_000, "cost_total": 300, "margin": 700,
    }
    assert [row.name for row in report.low_stock] == ["Olma", "Paket"]
    assert [(row.name, row.checks, row.total) for row in report.cashiers] == [
        ("Kassir Ali", 2, 950),
        ("Rahbar", 1, 400),
    ]
    assert [(row.name, row.orders, row.total) for row in report.waiters] == [
        ("Ofitsiant Lola", 1, 300),
    ]


async def test_report_is_business_scoped_and_requires_statistics_permission(
    statistics_context,
):
    service, _engine = statistics_context

    report = await service.report(
        business_account_id=2,
        permissions=None,
        period="kun",
        anchor="2026-08-04",
    )
    assert report.revenue == 999_999
    assert report.expenses == 700_000
    assert [row.name for row in report.low_stock] == ["Begona tovar"]

    with pytest.raises(ApiError) as forbidden:
        await service.report(
            business_account_id=1,
            permissions=("kassa",),
            period="kun",
            anchor="2026-08-04",
        )
    assert forbidden.value.code == "staff_permission_required"


async def test_related_staff_and_inventory_fallbacks_are_tenant_scoped(
    statistics_context,
):
    service, engine = statistics_context
    with Session(engine) as seed:
        seed.add(staff(21, 2, "Begona xodim"))
        foreign_cost_line = line(7, 6, 1, "Noma’lum", 10, 0)
        foreign_cost_line.inventory_item_id = 2001
        seed.add_all((
            receipt(
                6,
                1,
                source="manual",
                pay_type="naqd",
                staff_id=21,
                actor="Mahalliy kassir",
            ),
            foreign_cost_line,
            receipt(
                7,
                1,
                source="dining",
                pay_type="naqd",
                staff_id=11,
                actor="",
                waiter_id=21,
                waiter_name="Mahalliy ofitsiant",
            ),
            line(8, 7, 1, "Choy", 20, 0),
        ))
        seed.commit()

    report = await service.report(
        business_account_id=1,
        permissions=None,
        period="kun",
        anchor="2026-08-04",
    )

    assert report.cogs == 420
    assert "Begona xodim" not in {row.name for row in report.cashiers}
    assert "Begona xodim" not in {row.name for row in report.waiters}
    assert "Mahalliy kassir" in {row.name for row in report.cashiers}
    assert "Mahalliy ofitsiant" in {row.name for row in report.waiters}


async def test_period_labels_defaulting_and_navigation_match_v1656(statistics_context):
    service, _engine = statistics_context

    month = await service.report(
        business_account_id=1,
        permissions=("statistics",),
        period="noto‘g‘ri",
        anchor="noto‘g‘ri",
    )
    assert month.period == "oy"
    assert month.label == "Avg 2026"
    assert len(month.trend) == 31

    assert service.shift(period="kun", anchor="2026-08-04", direction=-1) == "2026-08-03"
    assert service.shift(period="hafta", anchor="2026-08-04", direction=1) == "2026-08-10"
    assert service.shift(period="chorak", anchor="2026-08-04", direction=-1) == "2026-04-01"
    assert service.shift(period="yarim", anchor="2026-08-04", direction=-1) == "2026-01-01"
    assert service.shift(period="yil", anchor="2026-08-04", direction=1) == "2027-01-01"

    assert await service.navigation(
        business_account_id=1,
        permissions=("statistics",),
        period="oy",
        anchor="2026-08-04",
        direction=-1,
    ) == "2026-07-01"


def test_fixture_has_no_accidental_duplicate_rows(statistics_context):
    _service, engine = statistics_context
    with Session(engine) as session:
        assert session.scalar(select(func.count(CashReceipt.id))) == 5
