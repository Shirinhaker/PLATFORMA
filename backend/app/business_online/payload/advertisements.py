"""Reklama narxini hisoblash."""

from __future__ import annotations

import re
from typing import Any

from app.business_online.payload.constants import (
    AD_DISTRICT_HOUR_RATE,
    AD_REGION_DISTRICT_COUNTS,
    AD_VALID_DURATIONS,
)
from app.business_online.payload.helpers import (
    integer_or_default,
)
from app.core.errors import ApiError


def advertisement_pricing(
    data: dict[str, Any],
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    raw_targets = data.get("targets")
    if not isinstance(raw_targets, list):
        raise ApiError(
            400, "advertisement_targets_required", "Reklama hududlarini tanlang."
        )
    targets: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for value in raw_targets[:30]:
        if not isinstance(value, dict):
            continue
        level = str(value.get("level") or "").strip().lower()
        region = str(value.get("region") or "").strip()
        district = str(value.get("district") or "").strip()
        if level not in {"district", "region", "republic"}:
            continue
        if level == "region" and region not in AD_REGION_DISTRICT_COUNTS:
            continue
        if level == "district" and (
            region not in AD_REGION_DISTRICT_COUNTS or not district
        ):
            continue
        if level == "republic":
            region = ""
            district = ""
        key = (level, region.casefold(), district.casefold())
        if key in seen:
            continue
        seen.add(key)
        targets.append({"level": level, "region": region, "district": district})
    if not targets:
        raise ApiError(
            400, "advertisement_targets_required", "Kamida bitta hudud tanlang."
        )
    if any(target["level"] == "republic" for target in targets) and len(targets) > 1:
        raise ApiError(
            400,
            "advertisement_republic_target_exclusive",
            "Respublika tanlansa boshqa hudud qo'shilmaydi.",
        )

    duration = integer_or_default(data.get("duration_days"), 1)
    if duration not in AD_VALID_DURATIONS:
        raise ApiError(
            400,
            "invalid_advertisement_duration",
            "Kunlar 1, 3, 7, 14 yoki 30 bo'lishi kerak.",
        )
    all_day = bool(data.get("daily_all_day"))
    if all_day:
        hours = 24
    else:
        start = full_advertisement_hour(data.get("daily_start"))
        end = full_advertisement_hour(data.get("daily_end"))
        if start == end:
            raise ApiError(
                400,
                "same_advertisement_hours",
                "Boshlanish va tugash soati bir xil bo'lmasin.",
            )
        hours = (end - start) % 24

    if any(target["level"] == "republic" for target in targets):
        district_count = sum(AD_REGION_DISTRICT_COUNTS.values())
    else:
        whole_regions = {
            target["region"] for target in targets if target["level"] == "region"
        }
        individual_districts = {
            (target["region"], target["district"].casefold())
            for target in targets
            if target["level"] == "district" and target["region"] not in whole_regions
        }
        district_count = sum(
            AD_REGION_DISTRICT_COUNTS[region] for region in whole_regions
        ) + len(individual_districts)
    billable = district_count * hours * duration
    return targets, {
        "district_count": district_count,
        "hours_per_day": hours,
        "duration_days": duration,
        "district_hour_rate": AD_DISTRICT_HOUR_RATE,
        "billable_district_hours": billable,
        "total": billable * AD_DISTRICT_HOUR_RATE,
        "currency": "UZS",
    }


def full_advertisement_hour(value: Any) -> int:
    text = str(value or "").strip()
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):00", text):
        raise ApiError(
            400,
            "invalid_advertisement_hour",
            "Vaqt faqat to'liq HH:00 soat bo'lishi kerak.",
        )
    return int(text[:2])
