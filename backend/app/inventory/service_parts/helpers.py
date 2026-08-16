"""Ombor uchun mayda hisoblar va konstantalar."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError

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
    return int((Decimal(total) / qty).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
