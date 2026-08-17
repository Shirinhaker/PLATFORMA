"""Moderatsiya uchun konstantalar."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError

"""Akkaunt cheklovlari, ichki izohlar va kontent ko'rinishi.

v1656 `moderation.py` bilan bir xil qoidalar:

- `content_hidden` egasining kabinetidagi ma'lumotni **o'chirmaydi**,
  faqat public qidiruv, xarita va takliflardan yashiradi;
- `account_blocked` yozish amallarini to'xtatadi;
- ikkalasi mustaqil — biri ikkinchisini yoqmaydi.

Har bir o'zgarish audit jurnaliga yoziladi.
"""


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def _require(value: str, allowed: tuple[str, ...], code: str, label: str) -> str:
    if value not in allowed:
        raise ApiError(400, code, label)
    return value


def _unix(value: datetime | None) -> int:
    return int(value.timestamp()) if value is not None else 0
