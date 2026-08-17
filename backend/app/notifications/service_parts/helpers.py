"""Bildirishnoma xizmati uchun konstantalar."""

from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


NowProvider = Callable[[], datetime]


PRICE_RE = re.compile(r"[\d][\d\s]*")


CATEGORY_NAMES = {
    "uy": "Uy-joy",
    "ish": "Ish o‘rinlari",
    "moshina": "Moshinalar",
    "hayvon": "Hayvonlar",
    "texnika": "Texnika",
    "boshqa": "Boshqalar",
}


def price_number(value: str) -> int | None:
    text = value.casefold().replace("\u00a0", " ")
    match = PRICE_RE.search(text)
    if match is None:
        return None
    number = int(re.sub(r"\s", "", match.group(0)) or 0)
    if not number:
        return None
    if "mln" in text or "million" in text:
        number *= 1_000_000
    elif "ming" in text:
        number *= 1_000
    return number
