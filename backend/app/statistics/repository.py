from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, and_, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cash_register.model import CashReceipt, CashReceiptLine
from app.catalog.model import CatalogItem
from app.expenses.model import Expense
from app.inventory.model import InventoryItem
from app.staff.model import StaffMember


class StatisticsRepository:
    @staticmethod
    def _effective_cost():
        fallback = cast(
            func.round(
                CashReceiptLine.qty
                * func.coalesce(InventoryItem.cost_price, 0)
            ),
            BigInteger,
        )
        return case(
            (CashReceiptLine.cost_total > 0, CashReceiptLine.cost_total),
            else_=fallback,
        )

    @staticmethod
    def _sales_filters(
        *, business_account_id: int, start: datetime, end: datetime
    ):
        return (
            CashReceipt.business_account_id == business_account_id,
            CashReceipt.created_at >= start,
            CashReceipt.created_at < end,
        )

    async def financial_summary(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        start: datetime,
        end: datetime,
    ):
        effective_cost = self._effective_cost()
        sale = CashReceipt.source != "debt_payment"
        cash_sale = sale & CashReceipt.pay_type.in_(("naqd", "karta"))
        statement = (
            select(
                func.coalesce(func.sum(case((sale, CashReceiptLine.total), else_=0)), 0).label("revenue"),
                func.coalesce(func.sum(case(
                    (
                        (CashReceipt.source == "debt_payment") | cash_sale,
                        CashReceiptLine.total,
                    ),
                    else_=0,
                )), 0).label("cash_in"),
                func.coalesce(func.sum(case((sale, effective_cost), else_=0)), 0).label("cogs"),
                func.coalesce(func.sum(case(
                    (CashReceipt.source == "debt_payment", CashReceiptLine.total),
                    else_=0,
                )), 0).label("qarzpay"),
            )
            .select_from(CashReceiptLine)
            .join(CashReceipt, CashReceipt.id == CashReceiptLine.receipt_id)
            .outerjoin(
                InventoryItem,
                and_(
                    InventoryItem.id == CashReceiptLine.inventory_item_id,
                    InventoryItem.business_account_id == business_account_id,
                ),
            )
            .where(*self._sales_filters(
                business_account_id=business_account_id,
                start=start,
                end=end,
            ))
        )
        return (await session.execute(statement)).one()

    async def payment_source_rows(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        start: datetime,
        end: datetime,
    ):
        return (await session.execute(
            select(
                CashReceipt.source,
                CashReceipt.pay_type,
                func.count(CashReceiptLine.id).label("line_count"),
                func.count(func.distinct(CashReceipt.id)).label("receipt_count"),
                func.coalesce(func.sum(CashReceiptLine.total), 0).label("total"),
            )
            .select_from(CashReceiptLine)
            .join(CashReceipt, CashReceipt.id == CashReceiptLine.receipt_id)
            .where(
                *self._sales_filters(
                    business_account_id=business_account_id,
                    start=start,
                    end=end,
                ),
                CashReceipt.source != "debt_payment",
            )
            .group_by(CashReceipt.source, CashReceipt.pay_type)
        )).all()

    async def sales_trend_rows(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        start: datetime,
        end: datetime,
        buckets: tuple[tuple[datetime, datetime], ...],
    ):
        bucket = case(
            *[
                (
                    (CashReceipt.created_at >= bucket_start)
                    & (CashReceipt.created_at < bucket_end),
                    index,
                )
                for index, (bucket_start, bucket_end) in enumerate(buckets)
            ],
            else_=None,
        )
        effective_cost = self._effective_cost()
        return (await session.execute(
            select(
                bucket.label("bucket"),
                func.coalesce(func.sum(CashReceiptLine.total), 0).label("revenue"),
                func.coalesce(func.sum(effective_cost), 0).label("cogs"),
            )
            .select_from(CashReceiptLine)
            .join(CashReceipt, CashReceipt.id == CashReceiptLine.receipt_id)
            .outerjoin(
                InventoryItem,
                and_(
                    InventoryItem.id == CashReceiptLine.inventory_item_id,
                    InventoryItem.business_account_id == business_account_id,
                ),
            )
            .where(
                *self._sales_filters(
                    business_account_id=business_account_id,
                    start=start,
                    end=end,
                ),
                CashReceipt.source != "debt_payment",
            )
            .group_by(bucket)
            .order_by(bucket)
        )).all()

    async def top_products(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        start: datetime,
        end: datetime,
    ):
        effective_cost = self._effective_cost()
        total = func.coalesce(func.sum(CashReceiptLine.total), 0)
        return (await session.execute(
            select(
                CashReceiptLine.item_name.label("name"),
                func.coalesce(func.sum(CashReceiptLine.qty), 0).label("qty"),
                func.min(CashReceiptLine.unit).label("unit"),
                total.label("total"),
                func.coalesce(func.sum(effective_cost), 0).label("cost_total"),
            )
            .select_from(CashReceiptLine)
            .join(CashReceipt, CashReceipt.id == CashReceiptLine.receipt_id)
            .outerjoin(
                InventoryItem,
                and_(
                    InventoryItem.id == CashReceiptLine.inventory_item_id,
                    InventoryItem.business_account_id == business_account_id,
                ),
            )
            .where(
                *self._sales_filters(
                    business_account_id=business_account_id,
                    start=start,
                    end=end,
                ),
                CashReceipt.source != "debt_payment",
            )
            .group_by(CashReceiptLine.item_name)
            .order_by(total.desc(), CashReceiptLine.item_name)
            .limit(12)
        )).all()

    async def employee_rows(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        start: datetime,
        end: datetime,
    ):
        name = func.coalesce(
            func.nullif(StaffMember.name, ""),
            func.nullif(CashReceipt.actor_name_snapshot, ""),
            "Rahbar",
        )
        total = func.coalesce(func.sum(CashReceiptLine.total), 0)
        statement = (
            select(
                name.label("name"),
                func.count(func.distinct(CashReceipt.id)).label("count"),
                total.label("total"),
            )
            .select_from(CashReceiptLine)
            .join(CashReceipt, CashReceipt.id == CashReceiptLine.receipt_id)
            .outerjoin(
                StaffMember,
                and_(
                    StaffMember.id == CashReceipt.created_by_staff_id,
                    StaffMember.business_account_id == business_account_id,
                ),
            )
            .where(
                *self._sales_filters(
                    business_account_id=business_account_id,
                    start=start,
                    end=end,
                ),
                CashReceipt.source != "debt_payment",
            )
        )
        return (await session.execute(
            statement
            .group_by(
                CashReceipt.created_by_staff_id,
                StaffMember.name,
                CashReceipt.actor_name_snapshot,
            )
            .order_by(total.desc(), name)
            .limit(12)
        )).all()

    async def waiter_rows(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        start: datetime,
        end: datetime,
    ):
        name = func.coalesce(
            func.nullif(StaffMember.name, ""),
            func.nullif(CashReceipt.waiter_name_snapshot, ""),
            "Rahbar",
        )
        total = func.coalesce(func.sum(CashReceiptLine.total), 0)
        return (await session.execute(
            select(
                name.label("name"),
                func.count(func.distinct(CashReceipt.id)).label("count"),
                total.label("total"),
            )
            .select_from(CashReceiptLine)
            .join(CashReceipt, CashReceipt.id == CashReceiptLine.receipt_id)
            .outerjoin(
                StaffMember,
                and_(
                    StaffMember.id == CashReceipt.waiter_staff_id,
                    StaffMember.business_account_id == business_account_id,
                ),
            )
            .where(
                *self._sales_filters(
                    business_account_id=business_account_id,
                    start=start,
                    end=end,
                ),
                CashReceipt.source == "dining",
            )
            .group_by(
                CashReceipt.waiter_staff_id,
                StaffMember.name,
                CashReceipt.waiter_name_snapshot,
            )
            .order_by(total.desc(), name)
            .limit(12)
        )).all()

    async def expense_rows(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        start: datetime,
        end: datetime,
        buckets: tuple[tuple[datetime, datetime], ...],
    ):
        bucket = case(
            *[
                (
                    (Expense.created_at >= bucket_start)
                    & (Expense.created_at < bucket_end),
                    index,
                )
                for index, (bucket_start, bucket_end) in enumerate(buckets)
            ],
            else_=None,
        )
        return (await session.execute(
            select(
                Expense.category,
                bucket.label("bucket"),
                func.coalesce(func.sum(Expense.amount), 0).label("amount"),
            )
            .where(
                Expense.business_account_id == business_account_id,
                Expense.created_at >= start,
                Expense.created_at < end,
            )
            .group_by(Expense.category, bucket)
            .order_by(Expense.category, bucket)
        )).all()

    async def low_stock(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
    ):
        return (await session.execute(
            select(
                CatalogItem.name,
                CatalogItem.unit,
                InventoryItem.stock_qty,
            )
            .select_from(InventoryItem)
            .join(
                CatalogItem,
                and_(
                    CatalogItem.id == InventoryItem.catalog_item_id,
                    CatalogItem.business_account_id == business_account_id,
                ),
            )
            .where(
                InventoryItem.business_account_id == business_account_id,
                InventoryItem.track_stock.is_(True),
            )
            .order_by(InventoryItem.stock_qty, InventoryItem.id)
            .limit(8)
        )).all()
