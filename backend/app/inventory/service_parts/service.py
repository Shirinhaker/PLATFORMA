"""`InventoryService` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.inventory.service_parts.base import InventoryServiceBase
from app.inventory.service_parts.cash_lines import CashLinesMixin
from app.inventory.service_parts.items import ItemsMixin
from app.inventory.service_parts.moves import MovesMixin
from app.inventory.service_parts.production import ProductionMixin


class InventoryService(
    CashLinesMixin,
    ItemsMixin,
    MovesMixin,
    ProductionMixin,
    InventoryServiceBase,
):
    """Ombor bo'yicha barcha amallar."""
