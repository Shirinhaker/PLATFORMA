"""Kassa: to'lov, hisobni tahrirlash, yakunlash, bekor qilish.

Eng katta bo'lim — to'lov tasdiqlanganda ombor FIFO bo'yicha
yechiladi, chek yoziladi va qarz hisobga olinadi.
"""

from __future__ import annotations

from app.cash_register.model import CashReceipt, CashReceiptLine
from app.core.errors import ApiError
from app.dining.schemas import (
    DiningCancel,
    DiningCashierItemsUpdate,
    DiningOrderRead,
    DiningPaymentCreate,
    DiningPaymentResult,
)
from app.dining.service_parts.base import DiningServiceBase
from app.dining.service_parts.helpers import (
    _line_total,
    _quantity,
)


class CashierMixin(DiningServiceBase):
    async def confirm_payment(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        order_id: int,
        actor_staff_id: int | None,
        body: DiningPaymentCreate,
    ) -> DiningPaymentResult:
        """To'lovni tasdiqlaydi: Kassa cheki, Ombor sarfi va kerak bo'lsa qarz.

        Uchalasi bitta tranzaksiyada yoziladi — chek yozilib, ombor
        yozilmay qolishi mumkin emas.
        """
        self._require(permissions, "payment_confirm", "kassa")
        now = self._now()
        async with self._session_factory() as session:
            order = await self._require_order(
                session,
                business_account_id=business_account_id,
                order_id=order_id,
                lock=True,
            )
            if order.payment_status == "confirmed":
                receipt_no = await self._receipt_no_for(session, order)
                return DiningPaymentResult(
                    pay_type=order.pay_type,
                    receipt_no=receipt_no,
                    already_confirmed=True,
                )
            if order.problem_open:
                raise ApiError(
                    409,
                    "dining_order_problem_open",
                    "Muammoli zakaz to‘lovi tasdiqlanmaydi. Avval muammoni hal qiling.",
                )
            if order.status != "active":
                raise ApiError(
                    409,
                    "dining_order_closed",
                    "Bu ichki buyurtma allaqachon yopilgan.",
                )
            items = await self._repository.items(session, order_id=order.id, lock=True)
            if not items:
                raise ApiError(
                    400,
                    "dining_order_empty",
                    "Bo‘sh hisob to‘lovi tasdiqlanmaydi.",
                )
            # Ombor qatorlarini bir tartibda qulflash — deadlockni oldini oladi.
            await self._inventory.lock_cash_catalog_items(
                session,
                business_account_id=business_account_id,
                catalog_item_ids=[
                    item.catalog_item_id
                    for item in items
                    if item.catalog_item_id is not None
                ],
            )
            receipt_no = await self._cash.next_receipt_no(
                session,
                business_account_id=business_account_id,
                now=now,
            )
            receipt = CashReceipt(
                business_account_id=business_account_id,
                receipt_no=receipt_no,
                source="dining",
                order_id=None,
                legacy_order_source_id=None,
                legacy_group_key=None,
                pay_type=body.pay_type,
                debtor_id=None,
                debtor_name_snapshot="",
                legacy_debtor_source_id=None,
                note=f"Ichki buyurtma #{order.id}",
                created_by_staff_id=actor_staff_id,
                actor_name_snapshot=await self._actor_name(session, actor_staff_id),
                waiter_staff_id=order.waiter_staff_id,
                waiter_name_snapshot=order.waiter_name,
                created_at=now,
            )
            session.add(receipt)
            await session.flush()

            if body.pay_type == "qarz":
                if body.debtor_id is None:
                    raise ApiError(
                        400,
                        "debt_debtor_required",
                        "Qarz uchun qarzdorni tanlang.",
                    )
                debtor = await self._debt_ledger.require_debtor_in_session(
                    session,
                    business_account_id=business_account_id,
                    debtor_id=body.debtor_id,
                    lock=True,
                )
                await self._debt_ledger.create_transaction_in_session(
                    session,
                    business_account_id=business_account_id,
                    debtor_id=debtor.id,
                    transaction_type="debt",
                    amount=order.total,
                    transaction_date=now.date(),
                    note=f"Ichki buyurtma #{order.id}",
                    actor_staff_id=actor_staff_id,
                    cash_receipt_id=receipt.id,
                    debtor=debtor,
                )
                receipt.debtor_id = debtor.id
                receipt.debtor_name_snapshot = debtor.name
                receipt.legacy_debtor_source_id = debtor.legacy_source_id
                order.debtor_id = debtor.id

            for item in items:
                line = CashReceiptLine(
                    receipt_id=receipt.id,
                    business_account_id=business_account_id,
                    catalog_item_id=item.catalog_item_id,
                    inventory_item_id=None,
                    legacy_source_key=None,
                    item_name=item.name,
                    qty=item.qty,
                    unit=item.unit,
                    unit_price=item.price,
                    total=item.total,
                    cost_total=0,
                    created_at=now,
                )
                session.add(line)
                await session.flush()
                if item.catalog_item_id is None:
                    continue
                inventory_id, cost = await self._inventory.consume_cash_line(
                    session,
                    business_account_id=business_account_id,
                    catalog_item_id=item.catalog_item_id,
                    cash_sale_line_id=line.id,
                    qty=item.qty,
                    actor_staff_id=actor_staff_id,
                    note=f"Ichki buyurtma #{order.id}",
                    now=now,
                )
                line.inventory_item_id = inventory_id
                line.cost_total = cost

            # Ombor sarfi va chek qatorlari yozilib bo'lgach holat
            # o'zgaradi — bildirishnoma yuborilishidan oldin.
            await session.flush()
            order.payment_status = "confirmed"
            order.pay_type = body.pay_type
            order.cash_receipt_id = receipt.id
            order.updated_at = now
            await self._notify(
                session,
                business_account_id=business_account_id,
                event_key=f"dining:{order.id}:paid:kitchen",
                title="Ichki zakaz to‘lovi tasdiqlandi",
                body_text=(f"Zakaz #{order.id} to‘lovi kassir tomonidan tasdiqlandi."),
                action_type="dining_kitchen",
                order_id=order.id,
                target_perm="kitchen",
                now=now,
                requires_action=False,
            )
            await self._resolve(
                session,
                business_account_id=business_account_id,
                order_id=order.id,
                action_type="dining_cash",
                now=now,
            )
            await session.commit()
        return DiningPaymentResult(pay_type=body.pay_type, receipt_no=receipt_no)

    async def update_cashier_items(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        order_id: int,
        body: DiningCashierItemsUpdate,
    ) -> DiningOrderRead:
        """Kassir hisob yopilguncha qator miqdorini o'zgartiradi."""
        self._require(permissions, "kassa")
        now = self._now()
        async with self._session_factory() as session:
            order = await self._require_order(
                session,
                business_account_id=business_account_id,
                order_id=order_id,
                lock=True,
            )
            if order.status != "active" or order.payment_status == "confirmed":
                raise ApiError(
                    400,
                    "dining_order_closed",
                    "Yopilgan hisobni tahrirlab bo‘lmaydi.",
                )
            rows = {
                item.id: item
                for item in await self._repository.items(
                    session, order_id=order.id, lock=True
                )
            }
            for change in body.items:
                item = rows.get(change.line_id)
                if item is None:
                    continue
                if change.qty <= 0:
                    await session.delete(item)
                    rows.pop(change.line_id)
                    continue
                item.qty = _quantity(change.qty, item.unit)
                item.total = _line_total(item.price, item.qty)
            total = sum(item.total for item in rows.values())
            if total <= 0:
                # Rollback'dan keyin ORM obyektlarini o'qish mumkin emas,
                # shuning uchun xabar oldindan tayyor.
                await session.rollback()
                raise ApiError(
                    400,
                    "dining_order_empty",
                    "Hisobda kamida bitta taom qolishi kerak.",
                )
            order.total = total
            order.updated_at = now
            place_name, place_kind = await self._place_of(session, order)
            items = await self._repository.items(session, order_id=order.id)
            result = self._order_read(order, place_name, place_kind, items)
            await session.commit()
        return result

    async def finalize(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        order_id: int,
    ) -> DiningOrderRead:
        """Hisobni yopadi va stolni bo'shatadi."""
        self._require(permissions, "kassa", "payment_confirm")
        now = self._now()
        async with self._session_factory() as session:
            order = await self._require_order(
                session,
                business_account_id=business_account_id,
                order_id=order_id,
                lock=True,
            )
            place_name, place_kind = await self._place_of(session, order)
            if order.status == "done":
                items = await self._repository.items(session, order_id=order.id)
                return self._order_read(order, place_name, place_kind, items)
            if order.problem_open:
                raise ApiError(
                    409,
                    "dining_order_problem_open",
                    "Muammoli zakazni yakunlab bo‘lmaydi. Avval muammoni hal qiling.",
                )
            if order.payment_status != "confirmed":
                raise ApiError(
                    409,
                    "dining_payment_required",
                    "Avval to‘lovni tasdiqlang.",
                )
            if order.kitchen_status != "done":
                raise ApiError(
                    409,
                    "dining_kitchen_pending",
                    "Oshpaz buyurtmani hali tayyor qilmagan.",
                )
            order.status = "done"
            order.updated_at = now
            items = await self._repository.items(session, order_id=order.id)
            result = self._order_read(order, place_name, place_kind, items)
            await session.commit()
        return result

    async def cancel(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        order_id: int,
        body: DiningCancel,
    ) -> DiningOrderRead:
        """To'lovi tasdiqlanmagan zakazni bekor qiladi."""
        self._require(permissions, "kassa")
        now = self._now()
        async with self._session_factory() as session:
            order = await self._require_order(
                session,
                business_account_id=business_account_id,
                order_id=order_id,
                lock=True,
            )
            if order.payment_status == "confirmed":
                raise ApiError(
                    409,
                    "dining_order_paid",
                    "To‘lovi tasdiqlangan ichki buyurtmani bekor qilib bo‘lmaydi.",
                )
            if order.status != "active":
                raise ApiError(
                    409,
                    "dining_order_closed",
                    "Bu ichki buyurtma allaqachon yopilgan.",
                )
            order.status = "cancelled"
            order.problem_open = False
            order.problem_reason = "Bekor qilindi"
            order.problem_note = body.reason.strip()
            order.updated_at = now
            place_name, place_kind = await self._place_of(session, order)
            await self._resolve(
                session,
                business_account_id=business_account_id,
                order_id=order.id,
                action_type=None,
                now=now,
            )
            await self._notify(
                session,
                business_account_id=business_account_id,
                event_key=f"dining:{order.id}:cancelled:kitchen",
                title="Ichki zakaz bekor qilindi",
                body_text=f"{place_name} · {order.problem_note}",
                action_type="dining_cancelled",
                order_id=order.id,
                target_perm="kitchen",
                now=now,
                requires_action=False,
            )
            items = await self._repository.items(session, order_id=order.id)
            result = self._order_read(order, place_name, place_kind, items)
            await session.commit()
        return result
