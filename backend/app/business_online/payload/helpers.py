"""Payload ustidagi mayda amallar: qidirish, tozalash, tur o'girish.

Bu funksiyalar hech qanday domenni bilmaydi — ular faqat lug'at va
ro'yxat bilan ishlaydi.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from math import isfinite
from typing import Any

from app.business_online.payload.constants import (
    OWNERSHIP_FIELDS,
    SENSITIVE_NAMES,
    SENSITIVE_SUFFIXES,
)
from app.core.errors import ApiError


def normalized_payload(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def raw_payload_rows(payload: Any, resource: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    value = payload.get(resource)
    if not isinstance(value, list):
        return []
    return [deepcopy(row) for row in value if isinstance(row, dict)]


def normalized_integer_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    result: list[int] = []
    for item in value:
        identifier = integer(item)
        if identifier and identifier not in result:
            result.append(identifier)
    return result


def queue_enabled(value: Any) -> bool:
    return value is True or str(value).strip().casefold() in {"1", "true", "on"}


def sanitize_mapping(value: dict[str, Any], *, allow_id: bool) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ApiError(422, "invalid_record", "Yozuv obyekt bo‘lishi kerak.")
    if len(value) > 100:
        raise ApiError(422, "record_too_large", "Yozuvda maydonlar juda ko‘p.")
    result: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        lowered = key.casefold()
        if not key or len(key) > 80:
            raise ApiError(422, "invalid_record_key", "Yozuv maydoni noto‘g‘ri.")
        if lowered in SENSITIVE_NAMES or lowered.endswith(SENSITIVE_SUFFIXES):
            raise ApiError(
                422,
                "sensitive_record_field",
                "Maxfiy maydonni kabinet yozuviga saqlash mumkin emas.",
            )
        if lowered in OWNERSHIP_FIELDS or (lowered == "id" and not allow_id):
            continue
        result[key] = sanitize_value(raw_value, depth=0)
    return result


def sanitize_value(value: Any, *, depth: int) -> Any:
    if depth > 5:
        raise ApiError(422, "record_too_deep", "Yozuv tuzilmasi juda chuqur.")
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if isfinite(value) else None
    if isinstance(value, str):
        if len(value) > 20_000:
            raise ApiError(422, "record_value_too_long", "Matn juda uzun.")
        return value
    if isinstance(value, list):
        if len(value) > 500:
            raise ApiError(422, "record_list_too_long", "Ro‘yxat juda uzun.")
        return [sanitize_value(item, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        return {
            str(key): sanitize_value(item, depth=depth + 1)
            for key, item in value.items()
            if str(key).casefold() not in SENSITIVE_NAMES
            and not str(key).casefold().endswith(SENSITIVE_SUFFIXES)
        }
    return str(value)


def next_record_id(rows: list[dict[str, Any]]) -> int:
    identifiers = []
    for row in rows:
        try:
            identifiers.append(int(row.get("id") or 0))
        except (TypeError, ValueError):
            continue
    return max(identifiers, default=0) + 1


def find_record(
    rows: list[dict[str, Any]],
    record_id: int | str,
) -> dict[str, Any]:
    return rows[find_record_index(rows, record_id)]


def find_record_index(
    rows: list[dict[str, Any]],
    record_id: int | str,
) -> int:
    expected = str(record_id)
    for index, row in enumerate(rows):
        if str(row.get("id")) == expected:
            return index
    raise ApiError(404, "business_online_record_not_found", "Yozuv topilmadi.")


def find_resource_record(
    rows: list[dict[str, Any]],
    record_id: int | str,
    resource: str,
) -> dict[str, Any]:
    return rows[find_resource_record_index(rows, record_id, resource)]


def find_resource_record_index(
    rows: list[dict[str, Any]],
    record_id: int | str,
    resource: str,
) -> int:
    try:
        return find_record_index(rows, record_id)
    except ApiError:
        if resource == "dining_places":
            raise ApiError(
                404,
                "dining_place_not_found",
                "Stol yoki xona topilmadi.",
            ) from None
        if resource == "medical_doctors":
            raise ApiError(
                404,
                "medical_provider_not_found",
                "Xizmat ko'rsatuvchi topilmadi.",
            ) from None
        if resource == "medical_queue":
            raise ApiError(
                404,
                "medical_queue_not_found",
                "Navbat topilmadi.",
            ) from None
        raise


def missing_record_id() -> ApiError:
    return ApiError(422, "record_id_required", "Amal uchun yozuv IDsi kerak.")


def action_forbidden() -> ApiError:
    return ApiError(
        403,
        "business_online_action_forbidden",
        "Bu bo‘limda tanlangan amal ruxsat etilmagan.",
    )


def order_is_service(row: dict[str, Any]) -> bool:
    return str(
        row.get("order_type") or row.get("kind") or row.get("order_category") or ""
    ) in {"booking", "service", "queue", "medical"}


def integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def integer_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_price_amount(value: Any) -> int:
    digits = "".join(character for character in str(value or "") if character.isdigit())
    return int(digits[:12]) if digits else 0


def unix_now() -> int:
    return int(datetime.now(UTC).timestamp())
