"""Ishlab chiqarish: retsept va tarix."""

from __future__ import annotations

from collections import defaultdict

from app.core.errors import ApiError
from app.inventory.schemas import (
    ProductionBatchRead,
    ProductionInputRead,
    RecipeIngredientRead,
)
from app.inventory.service_parts.base import InventoryServiceBase
from app.inventory.service_parts.helpers import (
    _money_total,
    _number,
)


class ProductionMixin(InventoryServiceBase):
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
                raise ApiError(
                    404, "inventory_ready_item_not_found", "Tayyor taom topilmadi."
                )
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
                        if show_costs
                        else 0
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
