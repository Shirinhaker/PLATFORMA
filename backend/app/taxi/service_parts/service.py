"""`TaxiService` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.taxi.service_parts.base import TaxiServiceBase
from app.taxi.service_parts.delivery import DeliveryMixin
from app.taxi.service_parts.drivers import DriversMixin
from app.taxi.service_parts.rides import RidesMixin


class TaxiService(
    DriversMixin,
    RidesMixin,
    DeliveryMixin,
    TaxiServiceBase,
):
    """Taksi va yetkazib berish bo'yicha barcha amallar."""
