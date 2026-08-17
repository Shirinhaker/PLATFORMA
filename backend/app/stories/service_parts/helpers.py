"""Storieslar uchun konstantalar."""

from __future__ import annotations

import math
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


NowProvider = Callable[[], datetime]


def _timestamp(value: object) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def rank_story_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        groups,
        key=lambda item: (
            0 if item.get("is_own") else 1,
            0 if item.get("has_unseen") else 1,
            0 if item.get("is_followed") else 1,
            (
                float(item["distance_km"])
                if item.get("distance_km") is not None
                else 1_000_000
            ),
            -_timestamp(item.get("latest_story_at")),
        ),
    )


def _distance_km(
    latitude: float | None,
    longitude: float | None,
    target_latitude: float | None,
    target_longitude: float | None,
) -> float | None:
    if None in (latitude, longitude, target_latitude, target_longitude):
        return None
    lat1, lng1, lat2, lng2 = map(
        float,
        (latitude, longitude, target_latitude, target_longitude),
    )
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    value = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
