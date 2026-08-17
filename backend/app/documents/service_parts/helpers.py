"""Hujjatlar xizmati uchun konstantalar."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


NowProvider = Callable[[], datetime]


COUNTERPARTY_TYPES = ("Yetkazib beruvchi", "Mijoz", "Hamkor", "Boshqa")


def _digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())
