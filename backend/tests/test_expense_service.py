from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.core.errors import ApiError
from app.db.base import Base
from app.expenses.model import Expense, ExpenseCategory
from app.expenses.schemas import ExpenseCategoryCreate, ExpenseCreate
from app.expenses.service import DEFAULT_EXPENSE_CATEGORIES, ExpenseService
from app.inventory.model import StockMove  # noqa: F401 -- FK metadata target


NOW = datetime(2026, 8, 4, 9, 30, tzinfo=UTC)


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

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


def account(identifier: int) -> Account:
    return Account(
        id=identifier,
        account_type=AccountType.BUSINESS,
        login=f"expense_business_{identifier}",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def expense_context():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(Account.__table__, ExpenseCategory.__table__, Expense.__table__),
    )
    with Session(engine) as seed:
        seed.add_all((account(1), account(2)))
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    service = ExpenseService(sessions, now_provider=lambda: NOW)
    try:
        yield service, engine
    finally:
        engine.dispose()


async def test_manual_expense_categories_daily_totals_and_delete(expense_context):
    service, engine = expense_context

    initial = await service.list_categories(
        business_account_id=1,
        permissions=None,
    )
    assert initial.categories == list(DEFAULT_EXPENSE_CATEGORIES)
    created_category = await service.create_category(
        business_account_id=1,
        permissions=None,
        body=ExpenseCategoryCreate(name="Reklama"),
    )
    assert created_category.exists is False
    duplicate = await service.create_category(
        business_account_id=1,
        permissions=None,
        body=ExpenseCategoryCreate(name="Reklama"),
    )
    assert duplicate.exists is True

    created = await service.create_expense(
        business_account_id=1,
        actor_staff_id=None,
        actor_name="Muhr",
        permissions=None,
        body=ExpenseCreate(category="Reklama", amount=75_000, note="Banner"),
    )
    await service.create_expense(
        business_account_id=2,
        actor_staff_id=None,
        actor_name="Begona biznes",
        permissions=None,
        body=ExpenseCreate(category="Reklama", amount=900_000, note="Begona"),
    )

    day = await service.list_expenses(
        business_account_id=1,
        permissions=None,
        day=None,
    )
    assert day.day.isoformat() == "2026-08-04"
    assert day.total == 75_000
    assert day.by_category == {"Reklama": 75_000}
    assert [(row.id, row.who, row.note) for row in day.expenses] == [
        (created.id, "Muhr", "Banner")
    ]

    await service.delete_expense(
        business_account_id=1,
        permissions=None,
        expense_id=created.id,
    )
    with Session(engine) as session:
        assert session.get(Expense, created.id) is None
        assert session.scalar(select(func.count(Expense.id))) == 1


async def test_stock_expense_is_immutable_and_business_scoped(expense_context):
    service, engine = expense_context
    with Session(engine) as seed:
        seed.add(Expense(
            id=10,
            business_account_id=1,
            legacy_source_id=10,
            category="Tovar xaridi",
            amount=250_000,
            note="Un",
            source="stock",
            inventory_stock_move_id=None,
            performed_by_staff_id=None,
            actor_name_snapshot="",
            created_at=NOW,
        ))
        seed.commit()

    with pytest.raises(ApiError) as locked:
        await service.delete_expense(
            business_account_id=1,
            permissions=None,
            expense_id=10,
        )
    assert locked.value.code == "expense_stock_locked"

    with pytest.raises(ApiError) as foreign:
        await service.delete_expense(
            business_account_id=2,
            permissions=None,
            expense_id=10,
        )
    assert foreign.value.code == "expense_not_found"

    with pytest.raises(ApiError) as forbidden:
        await service.list_expenses(
            business_account_id=1,
            permissions=("kassa",),
            day=None,
        )
    assert forbidden.value.code == "staff_permission_required"
