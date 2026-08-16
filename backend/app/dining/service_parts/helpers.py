"""Ovqatlanish xizmati uchun mayda hisoblar: narx, miqdor, vaqt."""

from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

"""Ovqatlanish zanjiri: ofitsiant → oshpaz → kassa → ombor.

Oqim v1656 (`api.py:3503-3860`) bilan bir xil:

    ofitsiant stolga zakaz ochadi
    → oshpaz "tayyor" deb belgilaydi
    → kassir to'lovni tasdiqlaydi (ombor va kassa shu payt yoziladi)
    → kassir hisobni yakunlaydi va stol bo'shaydi

Migratsiyagacha zanjirning oxirgi uchtasi umuman yo'q edi: `kitchen_status`
hech qachon `done`, `payment_status` hech qachon `confirmed` bo'lmagani
uchun stol abadiy band qolardi.
"""


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


QUANTITY_STEP = Decimal("0.001")


FRACTIONAL_UNITS = frozenset({"kg", "l", "litr", "gr", "gramm", "m", "m2", "m3"})


def _unix(value: datetime | None) -> int:
    return int(value.timestamp()) if value is not None else 0


def _price_of(value: str) -> int:
    digits = re.sub(r"[^0-9]", "", value or "")
    return int(digits[:12]) if digits else 0


def _quantity(value: Decimal, unit: str) -> Decimal:
    if (unit or "dona") not in FRACTIONAL_UNITS:
        rounded = value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        value = max(Decimal("1"), rounded)
    return value.quantize(QUANTITY_STEP, rounding=ROUND_HALF_EVEN)


def _line_total(price: int, qty: Decimal) -> int:
    return int((Decimal(price) * qty).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
