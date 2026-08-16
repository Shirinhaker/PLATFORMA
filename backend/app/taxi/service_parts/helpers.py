"""Taksi uchun konstantalar."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


NowProvider = Callable[[], datetime]


PRICING = {
    "taxi": {"base": 5_000, "per_km": 2_000, "min": 9_000},
    "dostavka": {"base": 10_000, "per_km": 2_500, "min": 15_000},
}


COMMISSION_PER_ORDER = 1_000


def calculate_price(kind: str, distance_km: float | None) -> int | None:
    if distance_km is None or distance_km <= 0:
        return None
    config = PRICING.get(kind, PRICING["taxi"])
    price = max(config["min"], config["base"] + config["per_km"] * distance_km)
    return int(price / 500 + 0.5) * 500
