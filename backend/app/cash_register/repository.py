from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.cash_register.model import (
    CashReceipt,
    CashReceiptCounter,
    CashReceiptLine,
)
from app.catalog.model import CatalogItem
from app.inventory.model import InventoryItem
from app.staff.model import StaffMember


class CashRegisterRepository:
    async def catalog_rows(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        catalog_item_ids: list[int] | None = None,
    ):
        statement = (
            select(CatalogItem, InventoryItem)
            .outerjoin(
                InventoryItem,
                (InventoryItem.catalog_item_id == CatalogItem.id)
                & (InventoryItem.business_account_id == business_account_id),
            )
            .where(
                CatalogItem.business_account_id == business_account_id,
                CatalogItem.status == "active",
            )
            .order_by(func.lower(CatalogItem.name), CatalogItem.id)
        )
        if catalog_item_ids is not None:
            if not catalog_item_ids:
                return []
            statement = statement.where(CatalogItem.id.in_(catalog_item_ids))
        return (await session.execute(statement)).all()

    async def next_receipt_no(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        now: datetime,
    ) -> int:
        bind = session.get_bind()
        if bind.dialect.name == "postgresql":
            statement = (
                postgresql_insert(CashReceiptCounter)
                .values(
                    business_account_id=business_account_id,
                    last_receipt_no=1,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=[CashReceiptCounter.business_account_id],
                    set_={
                        "last_receipt_no": CashReceiptCounter.last_receipt_no + 1,
                        "updated_at": now,
                    },
                )
                .returning(CashReceiptCounter.last_receipt_no)
            )
            return int(await session.scalar(statement))

        counter = await session.get(CashReceiptCounter, business_account_id)
        if counter is None:
            counter = CashReceiptCounter(
                business_account_id=business_account_id,
                last_receipt_no=1,
                updated_at=now,
            )
            session.add(counter)
        else:
            counter.last_receipt_no += 1
            counter.updated_at = now
        await session.flush()
        return int(counter.last_receipt_no)

    async def receipt_rows(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        start: datetime,
        end: datetime,
    ):
        return (await session.execute(
            select(CashReceipt, StaffMember.name)
            .outerjoin(StaffMember, StaffMember.id == CashReceipt.created_by_staff_id)
            .where(
                CashReceipt.business_account_id == business_account_id,
                CashReceipt.created_at >= start,
                CashReceipt.created_at < end,
            )
            .order_by(CashReceipt.created_at.desc(), CashReceipt.id.desc())
            .limit(200)
        )).all()

    async def lines_for_receipts(
        self,
        session: AsyncSession,
        receipt_ids: list[int],
    ) -> dict[int, list[CashReceiptLine]]:
        if not receipt_ids:
            return {}
        rows = list((await session.scalars(
            select(CashReceiptLine)
            .where(CashReceiptLine.receipt_id.in_(receipt_ids))
            .order_by(CashReceiptLine.receipt_id, CashReceiptLine.id)
        )).all())
        result: dict[int, list[CashReceiptLine]] = {
            receipt_id: [] for receipt_id in receipt_ids
        }
        for row in rows:
            result.setdefault(row.receipt_id, []).append(row)
        return result

    async def receipt(
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
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def receipt_by_order(
        self,
        session: AsyncSession,
        order_id: int,
        *,
        lock: bool = False,
    ) -> CashReceipt | None:
        statement = select(CashReceipt).where(CashReceipt.order_id == order_id)
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def receipt_lines(
        self,
        session: AsyncSession,
        receipt_id: int,
        *,
        lock: bool = False,
    ) -> list[CashReceiptLine]:
        statement = (
            select(CashReceiptLine)
            .where(CashReceiptLine.receipt_id == receipt_id)
            .order_by(CashReceiptLine.id)
        )
        if lock:
            statement = statement.with_for_update()
        return list((await session.scalars(statement)).all())
