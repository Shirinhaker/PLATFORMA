"""Navbat uchun vaqt hisoblari va tibbiy kod."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime, time, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


NowProvider = Callable[[], datetime]


UZBEKISTAN_TZ = timezone(timedelta(hours=5))


QUEUE_DIRECTIONS = frozenset(
    {
        "Transport va logistika",
        "Xizmat ko'rsatish",
        "Maishiy xizmatlar",
        "Qurilish",
        "Tibbiy xizmatlar",
        "Ko'chmas mulk",
        "Axborot texnologiyalari",
        "Konsalting va professional",
        "Madaniyat, sport, ko'ngilochar",
        "Turizm va mehmonxona",
        "Reklama va marketing",
        "Poligrafiya va nashriyot",
        "Moliyaviy faoliyat",
        "Import-eksport",
    }
)


TERMINAL_STATUSES = frozenset({"done", "cancelled", "no_show"})


def _clock(value: str) -> time:
    return time.fromisoformat(value)


def _clock_text(value: time | None) -> str:
    return value.strftime("%H:%M") if value is not None else ""


def _medical_code(name: str) -> str:
    letters = "".join(
        character for character in str(name or "").upper() if character.isalnum()
    )[:3]
    return letters or "NAV"


def _slot_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _generated_slots(start: time, end: time, step: int) -> list[time]:
    first = _slot_minutes(start)
    last = _slot_minutes(end)
    interval = max(5, int(step or 20))
    if first >= last:
        return []
    values: list[time] = []
    current = first
    while current + interval <= last:
        values.append(time(current // 60, current % 60))
        current += interval
    return values
