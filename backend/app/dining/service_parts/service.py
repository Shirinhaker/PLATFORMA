"""`DiningService` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.dining.service_parts.base import DiningServiceBase
from app.dining.service_parts.cashier import CashierMixin
from app.dining.service_parts.kitchen import KitchenMixin
from app.dining.service_parts.orders import OrdersMixin
from app.dining.service_parts.places import PlacesMixin
from app.dining.service_parts.problems import ProblemsMixin


class DiningService(
    PlacesMixin,
    OrdersMixin,
    KitchenMixin,
    CashierMixin,
    ProblemsMixin,
    DiningServiceBase,
):
    """Ovqatlanish zanjiri: stol -> zakaz -> oshxona -> kassa."""
