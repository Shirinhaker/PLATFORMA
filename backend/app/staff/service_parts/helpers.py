"""Xodimlar xizmati uchun konstantalar."""

from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime, time, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


NowProvider = Callable[[], datetime]


DEFAULT_PROFESSIONS = (
    "Sotuvchi",
    "Kassir",
    "Menejer",
    "Hisobchi",
    "Omborchi",
    "Yuk tashuvchi",
    "Haydovchi",
    "Farrosh",
    "Qorovul",
    "Boshqa",
)


LOGIN_RE = re.compile(r"^[a-z][a-z0-9_]{2,19}$")


UZBEKISTAN_TZ = timezone(timedelta(hours=5))


def _clock(value: str) -> time | None:
    return time.fromisoformat(value) if value else None


def _clock_text(value: time | None) -> str:
    return value.strftime("%H:%M") if value is not None else ""
