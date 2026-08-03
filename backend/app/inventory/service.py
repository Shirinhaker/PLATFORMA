from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.inventory.model import (
    InventoryItem,
    ProductionBatch,
    ProductionInput,
    RecipeIngredient,
    StockBatch,
    StockBatchConsumption,
    StockMove,
)
from app.inventory.repository import InventoryRepository
from app.inventory.schemas import (
    InventoryItemRead,
    InventoryItemWrite,
    InventoryListRead,
    ProductionBatchRead,
    ProductionInputRead,
    RecipeIngredientRead,
    StockMoveCreate,
    StockMoveRead,
    StockMoveResult,
)


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NowProvider = Callable[[], datetime]
FRACTIONAL_UNITS = frozenset({"kg", "g", "l", "ml", "metr", "m²", "m3"})
REASON_TEXT = {
    "kirim": "Kirim",
    "chiqim": "Chiqim",
    "sotuv": "Sotuv (buyurtma)",
    "tuzatish": "Tuzatish",
}
QUANTITY_STEP = Decimal("0.001")
RECIPE_STEP = Decimal("0.000001")
EPSILON = Decimal("0.000001")


def _quantity(value: object) -> Decimal:
    try:
        parsed = Decimal(str(value)).quantize(QUANTITY_STEP, rounding=ROUND_HALF_EVEN)
    except Exception:
        parsed = Decimal("0")
    if not parsed.is_finite() or abs(parsed) > Decimal("100000"):
        raise ApiError(422, "inventory_quantity_invalid", "Miqdor noto‘g‘ri.")
    return parsed


def _number(value: Decimal | int | float | None) -> float:
    return float(value or 0)


def _money_total(unit_cost: int, qty: Decimal) -> int:
    return int(
        (Decimal(unit_cost) * qty).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
    )


def _money_per_unit(total: int, qty: Decimal) -> int:
    if not qty:
        return 0
    return int(
        (Decimal(total) / qty).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
    )


class InventoryService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: InventoryRepository | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or InventoryRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def list_items(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
    ) -> InventoryListRead:
        self._require_any(permissions, "ombor", "production")
        show_costs = self._can_view_costs(permissions)
        async with self._session_factory() as session:
            rows = await self._repository.list_items(session, business_account_id)
            result = InventoryListRead(items=[
                self._item_read(row, show_costs=show_costs)
                for row in rows
            ])
            await session.rollback()
            return result

    async def configure_item(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        catalog_item_id: int,
        body: InventoryItemWrite,
    ) -> InventoryItemRead:
        self._require_any(permissions, "ombor")
        async with self._session_factory() as session:
            catalog = await self._repository.catalog_item(
                session,
                business_account_id=business_account_id,
                catalog_item_id=catalog_item_id,
            )
            if catalog is None:
                raise ApiError(
                    404,
                    "catalog_item_not_found",
                    "Mahsulot topilmadi.",
                )
            item = await self._repository.inventory_item_by_catalog(
                session,
                business_account_id=business_account_id,
                catalog_item_id=catalog_item_id,
                lock=True,
            )
            now = self._now_provider()
            if item is None:
                legacy_source_id = (
                    int(catalog.source_record_key)
                    if str(catalog.source_record_key or "").isdigit()
                    else None
                )
                item = InventoryItem(
                    business_account_id=business_account_id,
                    catalog_item_id=catalog.id,
                    legacy_source_id=legacy_source_id,
                    track_stock=body.track_stock,
                    stock_type=body.stock_type,
                    stock_qty=Decimal("0"),
                    cost_price=0,
                    min_qty=_quantity(body.min_qty),
                    fifo_initialized=True,
                    created_at=now,
                    updated_at=now,
                )
                session.add(item)
            else:
                item.track_stock = body.track_stock
                item.stock_type = body.stock_type
                item.min_qty = _quantity(body.min_qty)
                item.updated_at = now
            await session.flush()
            await session.commit()
            return InventoryItemRead(
                id=item.id,
                catalog_item_id=catalog.id,
                name=catalog.name,
                price=catalog.price_text,
                unit=catalog.unit or "dona",
                stock_qty=_number(item.stock_qty),
                cost_price=item.cost_price if self._can_view_costs(permissions) else 0,
                fifo_next_cost=0,
                fifo_value=0,
                min_qty=_number(item.min_qty),
                image_url="",
                group_id=catalog.catalog_group_id,
                group_name="",
                stock_type=item.stock_type,
                low_stock=item.stock_qty <= item.min_qty,
            )

    async def create_move(
        self,
        *,
        business_account_id: int,
        actor_staff_id: int | None,
        permissions: tuple[str, ...] | None,
        body: StockMoveCreate,
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
                        session.add(ProductionInput(
                            production_batch_id=production.id,
                            inventory_item_id=ingredient.id,
                            legacy_source_id=None,
                            qty=qty,
                            unit_cost=unit_cost,
                            total_cost=total,
                        ))
                        session.add(StockMove(
                            business_account_id=business_account_id,
                            inventory_item_id=ingredient.id,
                            legacy_source_id=None,
                            delta=-qty,
                            reason="chiqim",
                            note=f"Ishlab chiqarish #{production.id}: {catalog.name}"[:200],
                            cost=0,
                            legacy_order_source_id=None,
                            performed_by_staff_id=actor_staff_id,
                            created_at=now,
                        ))
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

                await session.flush()
                result = StockMoveResult(
                    move_id=move.id,
                    stock_qty=_number(item.stock_qty),
                    unit_cost=cost if self._can_view_costs(permissions) else 0,
                    total_cost=(
                        production_total
                        if inputs
                        else _money_total(cost, delta)
                    ) if self._can_view_costs(permissions) else 0,
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
                    raise ApiError(404, "inventory_move_not_found", "Harakat topilmadi.")
                owned = await self._repository.owned_item(
                    session,
                    business_account_id=business_account_id,
                    inventory_item_id=initial.inventory_item_id,
                    lock=True,
                )
                if owned is None:
                    raise ApiError(404, "inventory_item_not_found", "Mahsulot topilmadi.")
                item, _catalog = owned
                move = await self._repository.move(
                    session,
                    business_account_id=business_account_id,
                    move_id=move_id,
                    lock=True,
                )
                if move is None:
                    raise ApiError(404, "inventory_move_not_found", "Harakat topilmadi.")
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

    async def recipe(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        ready_inventory_item_id: int,
    ) -> list[RecipeIngredientRead]:
        self._require_any(permissions, "ombor", "production")
        show_costs = self._can_view_costs(permissions)
        async with self._session_factory() as session:
            owned = await self._repository.owned_item(
                session,
                business_account_id=business_account_id,
                inventory_item_id=ready_inventory_item_id,
            )
            if owned is None or owned[0].stock_type != "ready_food":
                raise ApiError(404, "inventory_ready_item_not_found", "Tayyor taom topilmadi.")
            rows = await self._repository.recipe_rows(
                session,
                business_account_id=business_account_id,
                ready_inventory_item_id=ready_inventory_item_id,
            )
            result = [
                RecipeIngredientRead(
                    item_id=ingredient.id,
                    qty_per_unit=_number(recipe.qty_per_unit),
                    name=catalog.name,
                    unit=catalog.unit or "dona",
                    cost_price=ingredient.cost_price if show_costs else 0,
                    cost_per_ready_unit=(
                        _money_total(ingredient.cost_price, recipe.qty_per_unit)
                        if show_costs else 0
                    ),
                )
                for recipe, ingredient, catalog in rows
            ]
            await session.rollback()
            return result

    async def production_history(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        limit: int,
    ) -> list[ProductionBatchRead]:
        self._require_any(permissions, "ombor", "production", "statistics")
        show_costs = self._can_view_costs(permissions)
        limit = max(1, min(200, int(limit or 50)))
        async with self._session_factory() as session:
            rows = await self._repository.production_rows(
                session,
                business_account_id=business_account_id,
                limit=limit,
            )
            batch_ids = [row[0].id for row in rows]
            inputs_by_batch: dict[int, list[ProductionInputRead]] = defaultdict(list)
            for value, name, unit in await self._repository.production_input_rows(
                session, batch_ids
            ):
                inputs_by_batch[value.production_batch_id].append(
                    ProductionInputRead(
                        item_id=value.inventory_item_id,
                        qty=_number(value.qty),
                        unit_cost=value.unit_cost if show_costs else 0,
                        total_cost=value.total_cost if show_costs else 0,
                        name=name,
                        unit=unit or "dona",
                    )
                )
            result = [
                ProductionBatchRead(
                    id=batch.id,
                    ready_item_id=batch.ready_inventory_item_id,
                    ready_name=ready_name,
                    ready_unit=ready_unit or "dona",
                    qty=_number(batch.qty),
                    total_cost=batch.total_cost if show_costs else 0,
                    unit_cost=batch.unit_cost if show_costs else 0,
                    note=batch.note,
                    who=str(staff_name or ""),
                    created_at=int(batch.created_at.timestamp()),
                    inputs=inputs_by_batch.get(batch.id, []),
                )
                for batch, ready_name, ready_unit, staff_name in rows
            ]
            await session.rollback()
            return result

    async def _production_inputs(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        body: StockMoveCreate,
        ready_item: InventoryItem,
        direction: str,
    ):
        if body.ingredients and body.delta <= 0:
            raise ApiError(
                422,
                "inventory_production_delta_invalid",
                "Ishlab chiqarishda tayyor mahsulot miqdori musbat bo‘lsin.",
            )
        if body.ingredients and ready_item.stock_type != "ready_food":
            raise ApiError(
                422,
                "inventory_production_target_invalid",
                "Xomashyo faqat tayyor taom kirimida sarflanadi.",
            )
        if not body.ingredients:
            if (
                body.delta > 0
                and ready_item.stock_type == "ready_food"
                and direction == "Umumiy ovqatlanish"
            ):
                raise ApiError(
                    422,
                    "inventory_production_inputs_required",
                    "Tayyor taom kirimi uchun sarflangan mahsulotlarni kiriting.",
                )
            return []
        quantities: dict[int, Decimal] = {}
        for row in body.ingredients:
            if row.item_id in quantities:
                raise ApiError(
                    422,
                    "inventory_ingredient_duplicate",
                    "Bir xomashyo retseptda bir marta kiritiladi.",
                )
            quantities[row.item_id] = _quantity(row.qty)
        result = []
        for item_id in sorted(quantities):
            owned = await self._repository.owned_item(
                session,
                business_account_id=business_account_id,
                inventory_item_id=item_id,
                lock=True,
            )
            if owned is None or not owned[0].track_stock or owned[0].stock_type != "raw_material":
                raise ApiError(
                    422,
                    "inventory_ingredient_invalid",
                    "Sarflangan xomashyo noto‘g‘ri tanlangan.",
                )
            qty = self._unit_quantity(quantities[item_id], owned[1].unit)
            if qty <= 0:
                raise ApiError(422, "inventory_quantity_invalid", "Miqdor noto‘g‘ri.")
            result.append((owned[0], owned[1], qty))
        return result

    async def _consume_fifo(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        item: InventoryItem,
        qty: Decimal,
        source_type: str,
        source_id: int,
        now: datetime,
        require_cost: bool,
    ) -> int:
        batches = await self._repository.fifo_batches(
            session,
            business_account_id=business_account_id,
            inventory_item_id=item.id,
            lock=True,
        )
        available = sum((batch.qty_remaining for batch in batches), Decimal("0"))
        if available + EPSILON < qty:
            raise ApiError(
                409,
                "inventory_fifo_insufficient",
                "FIFO partiyalarida qoldiq yetarli emas.",
            )
        left = qty
        for batch in batches:
            take = min(left, batch.qty_remaining)
            if take > 0 and require_cost and batch.unit_cost <= 0:
                raise ApiError(
                    409,
                    "inventory_fifo_cost_required",
                    "Eng eski FIFO partiyasida tannarx kiritilmagan.",
                )
            left -= take
            if left <= EPSILON:
                break
        left = qty
        total = 0
        for batch in batches:
            if left <= EPSILON:
                break
            take = min(left, batch.qty_remaining).quantize(
                QUANTITY_STEP, rounding=ROUND_HALF_UP
            )
            line_total = _money_total(batch.unit_cost, take)
            total += line_total
            batch.qty_remaining = _quantity(batch.qty_remaining - take)
            session.add(StockBatchConsumption(
                batch_id=batch.id,
                inventory_item_id=item.id,
                legacy_source_id=None,
                qty=take,
                unit_cost=batch.unit_cost,
                total_cost=line_total,
                source_type=source_type,
                source_id=source_id,
                created_at=now,
            ))
            left = _quantity(left - take)
        return total

    async def _restore_fifo(
        self,
        session: AsyncSession,
        *,
        source_type: str,
        source_id: int,
    ) -> None:
        rows = await self._repository.consumptions(
            session,
            source_type=source_type,
            source_id=source_id,
            lock=True,
        )
        batch_ids = sorted({row.batch_id for row in rows})
        batches = {}
        for batch_id in batch_ids:
            batch = await session.get(StockBatch, batch_id, with_for_update=True)
            if batch is None:
                raise ApiError(
                    409,
                    "inventory_fifo_restore_failed",
                    "FIFO partiyasi topilmadi; harakat qaytarilmadi.",
                )
            batches[batch_id] = batch
        for row in rows:
            batch = batches[row.batch_id]
            batch.qty_remaining = _quantity(batch.qty_remaining + row.qty)
        await self._repository.delete_consumptions(
            session,
            source_type=source_type,
            source_id=source_id,
        )

    @staticmethod
    def _add_batch(
        session: AsyncSession,
        *,
        business_account_id: int,
        item: InventoryItem,
        qty: Decimal,
        unit_cost: int,
        source_move_id: int,
        now: datetime,
    ) -> None:
        session.add(StockBatch(
            business_account_id=business_account_id,
            inventory_item_id=item.id,
            legacy_source_id=None,
            qty_in=qty,
            qty_remaining=qty,
            unit_cost=max(0, unit_cost),
            source_move_id=source_move_id,
            created_at=now,
        ))
        item.fifo_initialized = True

    @staticmethod
    def _unit_quantity(value: object, unit: str) -> Decimal:
        quantity = _quantity(value)
        if (unit or "dona") not in FRACTIONAL_UNITS:
            sign = Decimal("1") if quantity > 0 else Decimal("-1")
            quantity = sign * abs(quantity).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            quantity = quantity.quantize(QUANTITY_STEP)
        return quantity

    @staticmethod
    def _move_deletable(move: StockMove) -> bool:
        if move.legacy_order_source_id is not None:
            return False
        if move.reason not in {"kirim", "chiqim"}:
            return False
        return not move.note.startswith(("Kassa", "Chek", "Ishlab chiqarish"))

    @staticmethod
    def _require_any(
        permissions: tuple[str, ...] | None,
        *allowed: str,
    ) -> None:
        if permissions is None:
            return
        if not set(permissions).intersection(allowed):
            raise ApiError(
                403,
                "staff_permission_required",
                "Bu bo‘limga vakolatingiz yo‘q.",
            )

    @staticmethod
    def _can_view_costs(permissions: tuple[str, ...] | None) -> bool:
        return permissions is None or bool(
            {"expenses", "statistics"}.intersection(permissions)
        )

    @staticmethod
    def _item_read(row, *, show_costs: bool) -> InventoryItemRead:
        item, catalog, group_name, fifo_next_cost, fifo_value = row
        return InventoryItemRead(
            id=item.id,
            catalog_item_id=catalog.id,
            name=catalog.name,
            price=catalog.price_text if show_costs else "",
            unit=catalog.unit or "dona",
            stock_qty=_number(item.stock_qty),
            cost_price=item.cost_price if show_costs else 0,
            fifo_next_cost=int(fifo_next_cost or 0) if show_costs else 0,
            fifo_value=int(round(float(fifo_value or 0))) if show_costs else 0,
            min_qty=_number(item.min_qty),
            image_url="",
            group_id=catalog.catalog_group_id,
            group_name=str(group_name or ""),
            stock_type=item.stock_type,
            low_stock=item.stock_qty <= item.min_qty,
        )
