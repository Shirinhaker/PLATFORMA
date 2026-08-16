"""Ochiq qidiruv uchun konstantalar."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta, timezone

from app.cabinet_records.repository import CabinetRecordRepository

ImageUrlProvider = Callable[[str], str]

_cabinet_records = CabinetRecordRepository()

UZBEKISTAN_TZ = timezone(timedelta(hours=5))

_LOCATION_APOSTROPHES = ("‘", "’", "ʻ", "ʼ", "`", "´", "ʹ")

_LOCATION_SUFFIXES = (" viloyati", " tumani", " shahri")
