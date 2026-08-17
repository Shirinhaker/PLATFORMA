"""Cheklar: katalog, royxat, yaratish, ochirish."""

from __future__ import annotations

from datetime import date

from app.cash_register.model import CashReceipt, CashReceiptLine
from app.cash_register.schemas import (
    CashCatalogItemRead,
    CashReceiptCreate,
    CashReceiptCreated,
    CashReceiptRead,
    CashRegisterRead,
    CashTotalsRead,
)
from app.cash_register.service_parts.base import CashRegisterServiceBase
from app.cash_register.service_parts.helpers import (
    UZBEKISTAN_TZ,
    _money_total,
    _price,
    _quantity,
)
from app.core.errors import ApiError


class ReceiptsMixin(CashRegisterServiceBase):
    async def catalog(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
    ) -> list[CashCatalogItemRead]:
        self._require_kassa(permissions)
        async with self._session_factory() as session:
            rows = await self._repository.catalog_rows(
                session,
                business_account_id=business_account_id,
            )
            result = [
                CashCatalogItemRead(
                    id=catalog.id,
                    name=catalog.name,
                    price=_price(catalog.price_text),
                    price_text=catalog.price_text,
                    unit=catalog.unit or "dona",
                    track_stock=bool(inventory and inventory.track_stock),
                    stock_qty=float(inventory.stock_qty if inventory else 0),
                    low_stock=bool(
                        inventory
                        and inventory.track_stock
                        and inventory.stock_qty <= inventory.min_qty
                    ),
                )
                for catalog, inventory in rows
            ]
            await session.rollback()
            return result

    async def list_receipts(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        day: date | None,
    ) -> CashRegisterRead:
        self._require_kassa(permissions)
        selected_day, start, end = self._day_bounds(day)
        show_costs = permissions is None or bool(
            {"expenses", "statistics", "reports"}.intersection(permissions)
        )
        async with self._session_factory() as session:
            receipt_rows = await self._repository.receipt_rows(
                session,
                business_account_id=business_account_id,
                start=start,
                end=end,
            )
            receipts = [row[0] for row in receipt_rows]
            lines_by_receipt = await self._repository.lines_for_receipts(
                session,
                [receipt.id for receipt in receipts],
            )
            totals = CashTotalsRead()
            output: list[CashReceiptRead] = []
            for receipt, staff_name in receipt_rows:
                lines = lines_by_receipt.get(receipt.id, [])
                total = sum(line.total for line in lines)
                totals.all += total
                if receipt.source == "debt_payment":
                    totals.qarzpay += total
                    totals.cash_in += total
                elif receipt.pay_type in {"naqd", "karta", "qarz"}:
                    setattr(
                        totals,
                        receipt.pay_type,
                        getattr(totals, receipt.pay_type) + total,
                    )
                    if receipt.pay_type in {"naqd", "karta"}:
                        totals.cash_in += total
                else:
                    totals.order += total
                output.append(
                    self._receipt_read(
                        receipt,
                        lines,
                        staff_name=str(staff_name or ""),
                        show_costs=show_costs,
                    )
                )
            await session.rollback()
            return CashRegisterRead(
                day=selected_day,
                totals=totals,
                receipts=output,
            )

    async def create_receipt(
        self,
        *,
        business_account_id: int,
        actor_staff_id: int | None,
        actor_name: str,
        permissions: tuple[str, ...] | None,
        body: CashReceiptCreate,
    ) -> CashReceiptCreated:
        self._require_kassa(permissions)
        if body.pay_type == "qarz" and (
            self._debt_ledger is None or body.debtor_id is None
        ):
            raise ApiError(
                400,
                "debt_debtor_required",
                "Qarz uchun qarzdorni tanlang.",
            )
        now = self._sale_time(body.sale_date)
        async with self._session_factory() as session:
            try:
                debtor = None
                if body.pay_type == "qarz":
                    debtor = await self._debt_ledger.require_debtor_in_session(
                        session,
                        business_account_id=business_account_id,
                        debtor_id=body.debtor_id,
                    )
                requested = sorted(
                    {
                        item.catalog_item_id
                        for item in body.items
                        if item.catalog_item_id is not None
                    }
                )
                catalog_rows = await self._repository.catalog_rows(
                    session,
                    business_account_id=business_account_id,
                    catalog_item_ids=requested,
                )
                catalogs = {row[0].id: row[0] for row in catalog_rows}
                if len(catalogs) != len(requested):
                    raise ApiError(
                        404, "cash_catalog_item_not_found", "Mahsulot topilmadi."
                    )
                await self._inventory.lock_cash_catalog_items(
                    session,
                    business_account_id=business_account_id,
                    catalog_item_ids=requested,
                )
                prepared = []
                for item in body.items:
                    catalog = catalogs.get(item.catalog_item_id)
                    name = catalog.name if catalog is not None else item.name
                    if not name:
                        raise ApiError(
                            422,
                            "cash_item_name_required",
                            "Mahsulot nomi kiritilmadi.",
                        )
                    unit = (catalog.unit if catalog is not None else "dona") or "dona"
                    qty = _quantity(item.qty, unit)
                    total = _money_total(item.price, qty)
                    if total <= 0:
                        raise ApiError(
                            422,
                            "cash_price_required",
                            f"Narx kiritilmadi: {name}",
                        )
                    prepared.append(
                        (catalog, name[:220], unit[:40], qty, item.price, total)
                    )

                receipt_no = await self._repository.next_receipt_no(
                    session,
                    business_account_id=business_account_id,
                    now=now,
                )
                receipt = CashReceipt(
                    business_account_id=business_account_id,
                    receipt_no=receipt_no,
                    source="manual",
                    order_id=None,
                    legacy_order_source_id=None,
                    legacy_group_key=None,
                    pay_type=body.pay_type,
                    debtor_id=debtor.id if debtor is not None else None,
                    debtor_name_snapshot=debtor.name if debtor is not None else "",
                    legacy_debtor_source_id=(
                        debtor.legacy_source_id if debtor is not None else None
                    ),
                    note=body.note,
                    created_by_staff_id=actor_staff_id,
                    actor_name_snapshot=actor_name[:160],
                    created_at=now,
                )
                session.add(receipt)
                await session.flush()
                grand_total = 0
                debt_entries: list[tuple[int, str]] = []
                for catalog, name, unit, qty, price, total in prepared:
                    line = CashReceiptLine(
                        receipt_id=receipt.id,
                        business_account_id=business_account_id,
                        catalog_item_id=catalog.id if catalog is not None else None,
                        inventory_item_id=None,
                        legacy_source_key=None,
                        item_name=name,
                        qty=qty,
                        unit=unit,
                        unit_price=price,
                        total=total,
                        cost_total=0,
                        created_at=now,
                    )
                    session.add(line)
                    await session.flush()
                    if catalog is not None:
                        (
                            inventory_id,
                            cost_total,
                        ) = await self._inventory.consume_cash_line(
                            session,
                            business_account_id=business_account_id,
                            catalog_item_id=catalog.id,
                            cash_sale_line_id=line.id,
                            qty=qty,
                            actor_staff_id=actor_staff_id,
                            note=f"Chek #{receipt_no}",
                            now=now,
                        )
                        line.inventory_item_id = inventory_id
                        line.cost_total = cost_total
                    grand_total += total
                    if debtor is not None:
                        debt_entries.append((total, f"Kassa: {name}"[:200]))
                if debtor is not None:
                    await self._debt_ledger.replace_receipt_debts_in_session(
                        session,
                        business_account_id=business_account_id,
                        cash_receipt_id=receipt.id,
                        debtor_id=debtor.id,
                        entries=debt_entries,
                        actor_staff_id=actor_staff_id,
                        transaction_date=now.astimezone(UZBEKISTAN_TZ).date(),
                    )
                await session.flush()
                await session.commit()
                return CashReceiptCreated(
                    id=receipt.id,
                    receipt_no=receipt_no,
                    count=len(prepared),
                    total=grand_total,
                )
            except Exception:
                await session.rollback()
                raise

    async def delete_receipt(
        self,
        *,
        business_account_id: int,
        actor_staff_id: int | None,
        permissions: tuple[str, ...] | None,
        receipt_id: int,
    ) -> None:
        self._require_kassa(permissions)
        async with self._session_factory() as session:
            try:
                receipt = await self._repository.receipt(
                    session,
                    business_account_id=business_account_id,
                    receipt_id=receipt_id,
                    lock=True,
                )
                if receipt is None:
                    raise ApiError(404, "cash_receipt_not_found", "Chek topilmadi.")
                if receipt.source not in {"manual", "debt_payment"}:
                    raise ApiError(
                        409,
                        "cash_order_receipt_locked",
                        "Buyurtma orqali kelgan savdo bu yerdan o‘chirilmaydi.",
                    )
                lines = await self._repository.receipt_lines(
                    session, receipt.id, lock=True
                )
                now = self._now_provider()
                for line in lines:
                    if line.inventory_item_id is None:
                        continue
                    await self._inventory.restore_cash_line(
                        session,
                        business_account_id=business_account_id,
                        inventory_item_id=line.inventory_item_id,
                        cash_sale_line_id=line.id,
                        qty=line.qty,
                        actor_staff_id=actor_staff_id,
                        note=(
                            f"Chek #{receipt.receipt_no} o‘chirildi"
                            if receipt.receipt_no is not None
                            else f"Kassa #{receipt.id} o‘chirildi"
                        ),
                        now=now,
                    )
                await session.flush()
                if self._debt_ledger is not None:
                    await self._debt_ledger.delete_receipt_transactions_in_session(
                        session,
                        business_account_id=business_account_id,
                        cash_receipt_id=receipt.id,
                    )
                await session.delete(receipt)
                await session.flush()
                await session.commit()
            except Exception:
                await session.rollback()
                raise
