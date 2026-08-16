"""`OrderService` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.orders.service_parts.base import OrderServiceBase
from app.orders.service_parts.creation import CreationMixin
from app.orders.service_parts.listing import ListingMixin
from app.orders.service_parts.messaging import MessagingMixin
from app.orders.service_parts.payment import PaymentMixin
from app.orders.service_parts.problems import ProblemsMixin
from app.orders.service_parts.status import StatusMixin


class OrderService(
    CreationMixin,
    ListingMixin,
    StatusMixin,
    PaymentMixin,
    ProblemsMixin,
    MessagingMixin,
    OrderServiceBase,
):
    """Buyurtma bo'yicha barcha amallar."""
