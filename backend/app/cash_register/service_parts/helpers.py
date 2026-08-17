"""Kassa uchun konstantalar va vaqt hisoblari."""

from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


NowProvider = Callable[[], datetime]


UZBEKISTAN_TZ = timezone(timedelta(hours=5))


FRACTIONAL_UNITS = frozenset(
    {"kg", "g", "l", "litr", "ml", "metr", "sm", "m²", "m3", "soat"}
)


QUANTITY_STEP = Decimal("0.001")


PAY_TEXT = {
    "": "Buyurtma",
    "naqd": "Naqd",
    "karta": "Karta",
    "qarz": "Qarz",
}


def _quantity(value: object, unit: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except Exception as exc:
        raise ApiError(422, "cash_quantity_invalid", "Miqdor noto‘g‘ri.") from exc
    if not parsed.is_finite() or parsed <= 0 or parsed > Decimal("100000"):
        raise ApiError(422, "cash_quantity_invalid", "Miqdor noto‘g‘ri.")
    if (unit or "dona") not in FRACTIONAL_UNITS:
        parsed = parsed.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        parsed = max(Decimal("1"), parsed)
    return parsed.quantize(QUANTITY_STEP, rounding=ROUND_HALF_EVEN)


def _money_total(price: int, qty: Decimal) -> int:
    return int((Decimal(price) * qty).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def _price(value: str) -> int:
    digits = re.sub(r"[^0-9]", "", value or "")
    return int(digits[:12]) if digits else 0
