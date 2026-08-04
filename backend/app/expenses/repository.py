from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.expenses.model import Expense, ExpenseCategory


class ExpenseRepository:
    async def category_names(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
    ) -> list[str]:
        return list((await session.scalars(
            select(ExpenseCategory.name)
            .where(ExpenseCategory.business_account_id == business_account_id)
            .order_by(ExpenseCategory.name, ExpenseCategory.id)
        )).all())

    async def category(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        name: str,
    ) -> ExpenseCategory | None:
        return await session.scalar(
            select(ExpenseCategory).where(
                ExpenseCategory.business_account_id == business_account_id,
                ExpenseCategory.name == name,
            )
        )

    async def expenses_between(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        start: datetime,
        end: datetime,
        limit: int = 200,
    ):
        return list((await session.scalars(
            select(Expense)
            .where(
                Expense.business_account_id == business_account_id,
                Expense.created_at >= start,
                Expense.created_at < end,
            )
            .order_by(Expense.created_at.desc(), Expense.id.desc())
            .limit(limit)
        )).all())

    async def expense(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        expense_id: int,
        lock: bool = False,
    ) -> Expense | None:
        statement = select(Expense).where(
            Expense.id == expense_id,
            Expense.business_account_id == business_account_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def stock_expense(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        inventory_stock_move_id: int,
        lock: bool = False,
    ) -> Expense | None:
        statement = select(Expense).where(
            Expense.business_account_id == business_account_id,
            Expense.inventory_stock_move_id == inventory_stock_move_id,
            Expense.source == "stock",
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)
