"""Kassa cheki bilan bog'liq so'rovlar."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cash_register.model import CashReceipt, CashReceiptLine
from app.education.management_repository_parts.base import (
    EducationManagementRepositoryBase,
)


class CashMixin(EducationManagementRepositoryBase):
    async def clear_cash_receipt_lines(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        receipt_id: int,
    ) -> None:
        await session.execute(
            delete(CashReceiptLine).where(
                CashReceiptLine.business_account_id == business_account_id,
                CashReceiptLine.receipt_id == receipt_id,
            )
        )

    async def cash_receipt(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        receipt_id: int,
        lock: bool = False,
    ) -> CashReceipt | None:
        statement = select(CashReceipt).where(
            CashReceipt.id == receipt_id,
            CashReceipt.business_account_id == business_account_id,
            CashReceipt.source == "education",
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)
