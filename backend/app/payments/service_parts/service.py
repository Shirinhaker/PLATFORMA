"""`PaymentService` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.payments.service_parts.base import PaymentServiceBase
from app.payments.service_parts.catalog import CatalogMixin
from app.payments.service_parts.requests import RequestsMixin
from app.payments.service_parts.review import ReviewMixin


class PaymentService(
    CatalogMixin,
    RequestsMixin,
    ReviewMixin,
    PaymentServiceBase,
):
    """Tarif, obuna va to'lov arizalari."""
