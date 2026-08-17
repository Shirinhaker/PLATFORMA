"""Buyurtma tolovi va savdo yozuvi."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cash_register.model import CashReceipt, CashReceiptLine
from app.cash_register.schemas import (
    CashPaymentUpdate,
    CashReceiptRead,
)
from app.cash_register.service_parts.base import CashRegisterServiceBase
from app.cash_register.service_parts.helpers import (
    _price,
    _quantity,
)
from app.core.errors import ApiError
from app.orders.model import Order, OrderItem


class OrdersMixin(CashRegisterServiceBase):
    async def update_order_payment(
        self,
        *,
        business_account_id: int,
        actor_staff_id: int | None,
        permissions: tuple[str, ...] | None,
        receipt_id: int,
        body: CashPaymentUpdate,
    ) -> CashReceiptRead:
        self._require_kassa(permissions)
        if body.pay_type == "qarz" and (
            self._debt_ledger is None or body.debtor_id is None
        ):
            raise ApiError(
                400,
                "debt_debtor_required",
                "Qarz uchun qarzdorni tanlang.",
            )
        async with self._session_factory() as session:
            try:
                receipt = await self._repository.receipt(
                    session,
                    business_account_id=business_account_id,
                    receipt_id=receipt_id,
                    lock=True,
                )
                if receipt is None:
                    raise ApiError(404, "cash_receipt_not_found", "Savdo topilmadi.")
                if receipt.source != "order" or receipt.order_id is None:
                    raise ApiError(
                        409,
                        "cash_order_receipt_required",
                        "Bu faqat buyurtma savdosi uchun.",
                    )
                order = await session.get(Order, receipt.order_id, with_for_update=True)
                lines = await self._repository.receipt_lines(session, receipt.id)
                if body.pay_type == "qarz":
                    debtor = await self._debt_ledger.require_debtor_in_session(
                        session,
                        business_account_id=business_account_id,
                        debtor_id=body.debtor_id,
                        lock=True,
                    )
                    await self._debt_ledger.delete_receipt_transactions_in_session(
                        session,
                        business_account_id=business_account_id,
                        cash_receipt_id=receipt.id,
                    )
                    await self._debt_ledger.delete_order_debt_in_session(
                        session,
                        business_account_id=business_account_id,
                        order_id=receipt.order_id,
                    )
                    await self._debt_ledger.create_order_debt_in_session(
                        session,
                        business_account_id=business_account_id,
                        order_id=receipt.order_id,
                        debtor_id=debtor.id,
                        amount=sum(line.total for line in lines),
                        note=f"Tashqi buyurtma #{receipt.order_id}",
                        actor_staff_id=actor_staff_id,
                        cash_receipt_id=receipt.id,
                    )
                    receipt.debtor_id = debtor.id
                    receipt.debtor_name_snapshot = debtor.name
                    receipt.legacy_debtor_source_id = debtor.legacy_source_id
                else:
                    if self._debt_ledger is not None:
                        await self._debt_ledger.delete_receipt_transactions_in_session(
                            session,
                            business_account_id=business_account_id,
                            cash_receipt_id=receipt.id,
                        )
                        await self._debt_ledger.delete_order_debt_in_session(
                            session,
                            business_account_id=business_account_id,
                            order_id=receipt.order_id,
                        )
                    receipt.debtor_id = None
                    receipt.debtor_name_snapshot = ""
                    receipt.legacy_debtor_source_id = None
                receipt.pay_type = body.pay_type
                if order is not None:
                    order.pay_type = body.pay_type
                    order.debtor_id = receipt.debtor_id
                    order.updated_at = self._now_provider()
                await session.commit()
                return self._receipt_read(
                    receipt,
                    lines,
                    staff_name="",
                    show_costs=permissions is None,
                )
            except Exception:
                await session.rollback()
                raise

    async def post_order(
        self,
        session: AsyncSession,
        *,
        order: Order,
        actor_staff_id: int | None,
        actor_name: str = "",
    ) -> CashReceipt | None:
        """Buyurtma topshirilganda Kassa va Omborni tashqi tranzaksiyada yozadi."""
        if order.provider_kind != "business":
            return None
        existing = await self._repository.receipt_by_order(session, order.id, lock=True)
        if existing is not None:
            return existing
        order_items = list(
            (
                await session.scalars(
                    select(OrderItem)
                    .where(OrderItem.order_id == order.id)
                    .order_by(OrderItem.id)
                )
            ).all()
        )
        if not order_items:
            return None
        await self._inventory.lock_cash_catalog_items(
            session,
            business_account_id=order.provider_account_id,
            catalog_item_ids=[
                item.catalog_item_id
                for item in order_items
                if item.catalog_item_id is not None
            ],
        )
        now = self._now_provider()
        receipt = CashReceipt(
            business_account_id=order.provider_account_id,
            receipt_no=None,
            source="order",
            order_id=order.id,
            legacy_order_source_id=order.legacy_source_id,
            legacy_group_key=None,
            pay_type=order.pay_type,
            debtor_id=None,
            debtor_name_snapshot="",
            legacy_debtor_source_id=None,
            note=f"Buyurtma #{order.id}",
            created_by_staff_id=actor_staff_id,
            actor_name_snapshot=actor_name[:160],
            created_at=now,
        )
        session.add(receipt)
        await session.flush()
        if order.pay_type == "qarz":
            if self._debt_ledger is None or order.debtor_id is None:
                raise ApiError(
                    409,
                    "order_debt_missing",
                    "Buyurtmaning qarzdori topilmadi.",
                )
            debtor, _transaction = await self._debt_ledger.create_order_debt_in_session(
                session,
                business_account_id=order.provider_account_id,
                order_id=order.id,
                debtor_id=order.debtor_id,
                amount=order.total_amount,
                note=f"Tashqi buyurtma #{order.id}",
                actor_staff_id=actor_staff_id,
                cash_receipt_id=receipt.id,
            )
            receipt.debtor_id = debtor.id
            receipt.debtor_name_snapshot = debtor.name
            receipt.legacy_debtor_source_id = debtor.legacy_source_id
        for item in order_items:
            qty = _quantity(item.qty, item.unit or "dona")
            price = (
                int(
                    (Decimal(item.line_total) / qty).quantize(
                        Decimal("1"), rounding=ROUND_HALF_EVEN
                    )
                )
                if item.line_total
                else _price(item.price_text)
            )
            line = CashReceiptLine(
                receipt_id=receipt.id,
                business_account_id=order.provider_account_id,
                catalog_item_id=item.catalog_item_id,
                inventory_item_id=None,
                legacy_source_key=None,
                item_name=item.item_name,
                qty=qty,
                unit=item.unit or "dona",
                unit_price=price,
                total=item.line_total,
                cost_total=0,
                created_at=now,
            )
            session.add(line)
            await session.flush()
            if item.catalog_item_id is not None:
                inventory_id, total_cost = await self._inventory.consume_cash_line(
                    session,
                    business_account_id=order.provider_account_id,
                    catalog_item_id=item.catalog_item_id,
                    cash_sale_line_id=line.id,
                    qty=qty,
                    actor_staff_id=actor_staff_id,
                    note=f"Buyurtma #{order.id}",
                    now=now,
                )
                line.inventory_item_id = inventory_id
                line.cost_total = total_cost
        await session.flush()
        return receipt
