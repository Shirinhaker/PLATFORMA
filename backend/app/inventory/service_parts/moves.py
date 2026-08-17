"""Ombor harakatlari: kirim, chiqim, o'chirish."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN

from app.core.errors import ApiError
from app.inventory.model import (
    ProductionBatch,
    ProductionInput,
    RecipeIngredient,
    StockMove,
)
from app.inventory.schemas import (
    StockMoveCreate,
    StockMoveRead,
    StockMoveResult,
)
from app.inventory.service_parts.base import InventoryServiceBase
from app.inventory.service_parts.batches import BatchesMixin
from app.inventory.service_parts.helpers import (
    EPSILON,
    REASON_TEXT,
    RECIPE_STEP,
    _money_per_unit,
    _money_total,
    _number,
    _quantity,
)


class MovesMixin(BatchesMixin, InventoryServiceBase):
    async def create_move(
        self,
        *,
        business_account_id: int,
        actor_staff_id: int | None,
        permissions: tuple[str, ...] | None,
        body: StockMoveCreate,
        actor_name: str = "",
    ) -> StockMoveResult:
        self._require_any(permissions, "ombor", "production")
        async with self._session_factory() as session:
            try:
                owned = await self._repository.owned_item(
                    session,
                    business_account_id=business_account_id,
                    inventory_item_id=body.item_id,
                    lock=True,
                )
                if owned is None or not owned[0].track_stock:
                    raise ApiError(
                        404,
                        "inventory_item_not_found",
                        "Mahsulot topilmadi.",
                    )
                item, catalog = owned
                delta = self._unit_quantity(body.delta, catalog.unit)
                if delta == 0:
                    raise ApiError(
                        422,
                        "inventory_quantity_required",
                        "Miqdor kiritilmadi.",
                    )
                production_only = (
                    permissions is not None
                    and "production" in permissions
                    and "ombor" not in permissions
                )
                if production_only and not (
                    delta > 0 and item.stock_type == "ready_food"
                ):
                    raise ApiError(
                        403,
                        "inventory_production_only",
                        "Oshpaz faqat tayyor taom kirimini amalga oshira oladi.",
                    )

                direction = ""
                if delta > 0 and item.stock_type == "ready_food":
                    direction = await self._repository.business_direction(
                        session, business_account_id
                    )
                inputs = await self._production_inputs(
                    session,
                    business_account_id=business_account_id,
                    body=body,
                    ready_item=item,
                    direction=direction,
                )
                now = self._now_provider()
                reason = body.reason or ("kirim" if delta > 0 else "chiqim")
                cost = max(0, int(body.cost or 0))
                move = StockMove(
                    business_account_id=business_account_id,
                    inventory_item_id=item.id,
                    legacy_source_id=None,
                    delta=delta,
                    reason=reason,
                    note=body.note,
                    cost=cost,
                    legacy_order_source_id=None,
                    performed_by_staff_id=actor_staff_id,
                    created_at=now,
                )
                session.add(move)
                item.stock_qty = _quantity(item.stock_qty + delta)
                item.updated_at = now
                if delta > 0 and cost > 0:
                    item.cost_price = cost
                await session.flush()

                production_total = 0
                if inputs:
                    production = ProductionBatch(
                        business_account_id=business_account_id,
                        ready_inventory_item_id=item.id,
                        legacy_source_id=None,
                        qty=delta,
                        total_cost=0,
                        unit_cost=0,
                        note=body.note,
                        performed_by_staff_id=actor_staff_id,
                        created_at=now,
                    )
                    session.add(production)
                    await session.flush()
                    for ingredient, ingredient_catalog, qty in inputs:
                        total = await self._consume_fifo(
                            session,
                            business_account_id=business_account_id,
                            item=ingredient,
                            qty=qty,
                            source_type="production",
                            source_id=production.id,
                            now=now,
                            require_cost=True,
                        )
                        unit_cost = _money_per_unit(total, qty)
                        production_total += total
                        ingredient.stock_qty = _quantity(ingredient.stock_qty - qty)
                        ingredient.updated_at = now
                        session.add(
                            ProductionInput(
                                production_batch_id=production.id,
                                inventory_item_id=ingredient.id,
                                legacy_source_id=None,
                                qty=qty,
                                unit_cost=unit_cost,
                                total_cost=total,
                            )
                        )
                        session.add(
                            StockMove(
                                business_account_id=business_account_id,
                                inventory_item_id=ingredient.id,
                                legacy_source_id=None,
                                delta=-qty,
                                reason="chiqim",
                                note=f"Ishlab chiqarish #{production.id}: {catalog.name}"[
                                    :200
                                ],
                                cost=0,
                                legacy_order_source_id=None,
                                performed_by_staff_id=actor_staff_id,
                                created_at=now,
                            )
                        )
                    cost = _money_per_unit(production_total, delta)
                    production.total_cost = production_total
                    production.unit_cost = cost
                    item.cost_price = cost
                    move.cost = cost
                    move.note = (
                        f"Ishlab chiqarish #{production.id}"
                        + (f" — {body.note}" if body.note else "")
                    )[:200]
                    self._add_batch(
                        session,
                        business_account_id=business_account_id,
                        item=item,
                        qty=delta,
                        unit_cost=cost,
                        source_move_id=move.id,
                        now=now,
                    )
                    if body.save_recipe:
                        # Keyingi DELETE so‘rovi autoflush qiladi; barcha yangi
                        # ishlab chiqarish satrlari avval aniq ID olishi kerak.
                        await session.flush()
                        await self._repository.replace_recipe(
                            session,
                            business_account_id=business_account_id,
                            ready_inventory_item_id=item.id,
                            rows=[
                                RecipeIngredient(
                                    business_account_id=business_account_id,
                                    ready_inventory_item_id=item.id,
                                    ingredient_inventory_item_id=ingredient.id,
                                    legacy_source_id=None,
                                    qty_per_unit=(qty / delta).quantize(
                                        RECIPE_STEP, rounding=ROUND_HALF_EVEN
                                    ),
                                    updated_at=now,
                                )
                                for ingredient, _catalog, qty in inputs
                            ],
                        )
                elif delta > 0:
                    self._add_batch(
                        session,
                        business_account_id=business_account_id,
                        item=item,
                        qty=delta,
                        unit_cost=cost,
                        source_move_id=move.id,
                        now=now,
                    )
                else:
                    total = await self._consume_fifo(
                        session,
                        business_account_id=business_account_id,
                        item=item,
                        qty=abs(delta),
                        source_type="stock_move",
                        source_id=move.id,
                        now=now,
                        require_cost=False,
                    )
                    cost = _money_per_unit(total, abs(delta))
                    move.cost = cost

                if delta > 0 and cost > 0 and not inputs:
                    # SQLite servis testlari va PostgreSQL FK bog‘lanishi uchun
                    # barcha oldingi Ombor obyektlari avval aniq ID oladi.
                    await session.flush()
                    await self._expenses.create_stock_expense_in_session(
                        session,
                        business_account_id=business_account_id,
                        inventory_stock_move_id=move.id,
                        amount=_money_total(cost, delta),
                        note=(catalog.name + (f" — {body.note}" if body.note else "")),
                        actor_staff_id=actor_staff_id,
                        actor_name=actor_name,
                        created_at=now,
                    )

                await session.flush()
                result = StockMoveResult(
                    move_id=move.id,
                    stock_qty=_number(item.stock_qty),
                    unit_cost=cost if self._can_view_costs(permissions) else 0,
                    total_cost=(
                        production_total if inputs else _money_total(cost, delta)
                    )
                    if self._can_view_costs(permissions)
                    else 0,
                )
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise

    async def delete_move(
        self,
        *,
        business_account_id: int,
        actor_staff_id: int | None,
        permissions: tuple[str, ...] | None,
        move_id: int,
    ) -> None:
        del actor_staff_id
        self._require_any(permissions, "ombor")
        async with self._session_factory() as session:
            try:
                initial = await self._repository.move(
                    session,
                    business_account_id=business_account_id,
                    move_id=move_id,
                )
                if initial is None:
                    raise ApiError(
                        404, "inventory_move_not_found", "Harakat topilmadi."
                    )
                owned = await self._repository.owned_item(
                    session,
                    business_account_id=business_account_id,
                    inventory_item_id=initial.inventory_item_id,
                    lock=True,
                )
                if owned is None:
                    raise ApiError(
                        404, "inventory_item_not_found", "Mahsulot topilmadi."
                    )
                item, _catalog = owned
                move = await self._repository.move(
                    session,
                    business_account_id=business_account_id,
                    move_id=move_id,
                    lock=True,
                )
                if move is None:
                    raise ApiError(
                        404, "inventory_move_not_found", "Harakat topilmadi."
                    )
                if not self._move_deletable(move):
                    raise ApiError(
                        409,
                        "inventory_move_linked",
                        "Bu harakat buyurtma yoki kassa bilan bog‘liq — o‘chirib bo‘lmaydi.",
                    )
                if move.delta > 0:
                    batch = await self._repository.source_batch(
                        session, move.id, lock=True
                    )
                    if batch is not None and (
                        batch.qty_remaining + EPSILON < batch.qty_in
                    ):
                        raise ApiError(
                            409,
                            "inventory_batch_already_used",
                            "Bu FIFO partiyasidan mahsulot ishlatilgan — kirimni o‘chirib bo‘lmaydi.",
                        )
                    if batch is not None:
                        await session.delete(batch)
                else:
                    await self._restore_fifo(
                        session,
                        source_type="stock_move",
                        source_id=move.id,
                    )
                item.stock_qty = _quantity(item.stock_qty - move.delta)
                item.updated_at = self._now_provider()
                await self._expenses.delete_stock_expense_in_session(
                    session,
                    business_account_id=business_account_id,
                    inventory_stock_move_id=move.id,
                )
                await session.delete(move)
                await session.flush()
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def list_moves(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        inventory_item_id: int,
    ) -> list[StockMoveRead]:
        self._require_any(permissions, "ombor", "production")
        show_costs = self._can_view_costs(permissions)
        can_delete = permissions is None or "ombor" in permissions
        async with self._session_factory() as session:
            owned = await self._repository.owned_item(
                session,
                business_account_id=business_account_id,
                inventory_item_id=inventory_item_id,
            )
            if owned is None:
                raise ApiError(404, "inventory_item_not_found", "Mahsulot topilmadi.")
            item, catalog = owned
            rows = await self._repository.move_rows(
                session,
                business_account_id=business_account_id,
                inventory_item_id=item.id,
                limit=100,
            )
            result = [
                StockMoveRead(
                    id=move.id,
                    delta=_number(move.delta),
                    reason=move.reason,
                    reason_text=REASON_TEXT.get(move.reason, move.reason),
                    note=move.note,
                    who=str(staff_name or ""),
                    cost=move.cost if show_costs else 0,
                    can_delete=can_delete and self._move_deletable(move),
                    order_id=move.legacy_order_source_id,
                    created_at=int(move.created_at.timestamp()),
                    unit=catalog.unit or "dona",
                )
                for move, staff_name in rows
            ]
            await session.rollback()
            return result

    @staticmethod
    def _move_deletable(move: StockMove) -> bool:
        if move.legacy_order_source_id is not None:
            return False
        if move.reason not in {"kirim", "chiqim"}:
            return False
        return not move.note.startswith(("Kassa", "Chek", "Ishlab chiqarish"))
