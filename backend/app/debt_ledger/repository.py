from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.debt_ledger.model import Debtor, DebtTransaction


class DebtLedgerRepository:
    async def debtor(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        debtor_id: int,
        lock: bool = False,
    ) -> Debtor | None:
        statement = select(Debtor).where(
            Debtor.id == debtor_id,
            Debtor.business_account_id == business_account_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)
    async def debtors_with_balances(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
    ):
        balance = func.coalesce(func.sum(case(
            (DebtTransaction.transaction_type == "debt", DebtTransaction.amount),
            else_=-DebtTransaction.amount,
        )), 0)
        return (await session.execute(
            select(Debtor, balance.label("balance"))
            .outerjoin(
                DebtTransaction,
                DebtTransaction.debtor_id == Debtor.id,
            )
            .where(Debtor.business_account_id == business_account_id)
            .group_by(Debtor.id)
            .order_by(Debtor.created_at.desc(), Debtor.id.desc())
        )).all()

    async def transactions(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        debtor_id: int,
    ) -> list[DebtTransaction]:
        return list((await session.scalars(
            select(DebtTransaction)
            .where(
                DebtTransaction.business_account_id == business_account_id,
                DebtTransaction.debtor_id == debtor_id,
            )
            .order_by(
                DebtTransaction.transaction_date,
                DebtTransaction.id,
            )
        )).all())

    async def balance(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        debtor_id: int,
    ) -> int:
        value = await session.scalar(
            select(func.coalesce(func.sum(case(
                (DebtTransaction.transaction_type == "debt", DebtTransaction.amount),
                else_=-DebtTransaction.amount,
            )), 0)).where(
                DebtTransaction.business_account_id == business_account_id,
                DebtTransaction.debtor_id == debtor_id,
            )
        )
        return int(value or 0)

    async def transactions_for_receipt(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        cash_receipt_id: int,
        lock: bool = False,
    ) -> list[DebtTransaction]:
        statement = (
            select(DebtTransaction)
            .where(
                DebtTransaction.business_account_id == business_account_id,
                DebtTransaction.cash_receipt_id == cash_receipt_id,
            )
            .order_by(DebtTransaction.id)
        )
        if lock:
            statement = statement.with_for_update()
        return list((await session.scalars(statement)).all())

    async def order_debt(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        order_id: int,
        lock: bool = False,
    ) -> DebtTransaction | None:
        statement = select(DebtTransaction).where(
            DebtTransaction.business_account_id == business_account_id,
            DebtTransaction.order_id == order_id,
            DebtTransaction.transaction_type == "debt",
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)
