"""Moderatsiya uchun konstantalar."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def _require(value: str, allowed: tuple[str, ...], code: str, label: str) -> str:
    if value not in allowed:
        raise ApiError(400, code, label)
    return value


def _unix(value: datetime | None) -> int:
    return int(value.timestamp()) if value is not None else 0
