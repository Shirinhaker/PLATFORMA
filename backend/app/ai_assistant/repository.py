from datetime import datetime

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_assistant.model import AIChatMessage
from app.cash_register.model import CashReceipt, CashReceiptLine
from app.catalog.model import CatalogItem
from app.debt_ledger.model import DebtTransaction
from app.expenses.model import Expense
from app.inventory.model import InventoryItem
from app.orders.model import Order
from app.profiles.model import BusinessProfile


class AIAssistantRepository:
    async def business(self, session: AsyncSession, business_id: int) -> BusinessProfile | None:
        return await session.get(BusinessProfile, business_id)

    async def context(self, session: AsyncSession, business_id: int, start: datetime, end: datetime) -> dict:
        revenue = await session.scalar(
            select(func.coalesce(func.sum(CashReceiptLine.total), 0))
            .join(CashReceipt, CashReceipt.id == CashReceiptLine.receipt_id)
            .where(CashReceipt.business_account_id == business_id, CashReceipt.created_at >= start, CashReceipt.created_at < end)
        )
        expenses = await session.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.business_account_id == business_id, Expense.created_at >= start, Expense.created_at < end))
        debt = await session.scalar(select(func.coalesce(func.sum(case((DebtTransaction.transaction_type == "debt", DebtTransaction.amount), else_=-DebtTransaction.amount)), 0)).where(DebtTransaction.business_account_id == business_id))
        stock_rows = (await session.execute(
            select(CatalogItem.name, InventoryItem.stock_qty, CatalogItem.unit)
            .join(CatalogItem, CatalogItem.id == InventoryItem.catalog_item_id)
            .where(InventoryItem.business_account_id == business_id, InventoryItem.track_stock.is_(True), or_(InventoryItem.stock_qty <= InventoryItem.min_qty, InventoryItem.stock_qty <= 5))
            .order_by(InventoryItem.stock_qty, CatalogItem.name).limit(8)
        )).all()
        order_rows = (await session.execute(select(Order.status, func.count(Order.id)).where(Order.provider_account_id == business_id, Order.provider_kind == "business").group_by(Order.status))).all()
        return {
            "today_summary": {"revenue": int(revenue or 0), "expenses": int(expenses or 0), "profit": int(revenue or 0) - int(expenses or 0)},
            "debt_total": int(debt or 0),
            "low_stock": [{"name": r[0], "qty": float(r[1]), "unit": r[2] or "dona"} for r in stock_rows],
            "orders_by_status": {r[0]: int(r[1]) for r in order_rows},
        }

    async def history(self, session: AsyncSession, business_id: int, limit: int) -> list[AIChatMessage]:
        rows = list((await session.scalars(select(AIChatMessage).where(AIChatMessage.business_account_id == business_id).order_by(AIChatMessage.id.desc()).limit(limit))).all())
        return list(reversed(rows))
