"""Yozuv kimga tegishli ekanini aniqlash."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.legacy_migration.parity_v7.helpers import (
    _integer,
    _safe_row,
    _safe_rows,
)


def _attach_children(
    rows: Iterable[dict[str, object]],
    children_by_parent: dict[int, list[dict[str, object]]],
    child_key: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source_row in rows:
        row = _safe_row(source_row)
        row[child_key] = _safe_rows(
            children_by_parent.get(_integer(source_row.get("id")), [])
        )
        result.append(row)
    return result


def _filter_documents(rows: list[object], wanted: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        direction = str(row.get("direction") or "").strip().casefold()
        if (
            (
                wanted == "incoming"
                and (
                    "incoming" in direction
                    or "kirim" in direction
                    or "kiruvchi" in direction
                )
            )
            or (
                wanted == "outgoing"
                and (
                    "outgoing" in direction
                    or "chiq" in direction
                    or "chiquvchi" in direction
                )
            )
            or (
                wanted == "internal"
                and ("internal" in direction or "ichki" in direction)
            )
        ):
            result.append(row)
    return result


def _order_belongs_to_user(row: dict[str, object], user_id: int) -> bool:
    if "customer_kind" in row and str(row.get("customer_kind") or "user") != "user":
        return False
    candidate = (
        row.get("customer_user_id")
        or row.get("customer_actor_id")
        or row.get("user_id")
        or row.get("customer_id")
    )
    return _integer(candidate) == user_id


def _order_belongs_to_business(
    row: dict[str, object],
    business_id: int,
    owner_user_id: int,
) -> bool:
    if "provider_kind" in row:
        if str(row.get("provider_kind") or "business") != "business":
            return False
        return _integer(row.get("provider_actor_id")) == business_id
    return (
        _integer(row.get("business_id")) == business_id
        or _integer(row.get("provider_user_id")) == owner_user_id
    )


def _row_belongs_to_business(
    row: dict[str, object],
    business_id: int,
    owner_user_id: int,
) -> bool:
    if "owner_type" in row and str(row.get("owner_type") or "") == "business":
        return _integer(row.get("owner_id")) == business_id
    if "actor_type" in row and str(row.get("actor_type") or "") == "business":
        return _integer(row.get("business_id") or row.get("actor_id")) == business_id
    if "target_kind" in row and str(row.get("target_kind") or "") == "business":
        return _integer(row.get("target_id")) == business_id
    for key in (
        "business_id",
        "provider_actor_id",
        "sender_business_id",
        "actor_id",
    ):
        if key in row and _integer(row.get(key)) == business_id:
            return True
    return bool(
        owner_user_id
        and "user_id" in row
        and _integer(row.get("user_id")) == owner_user_id
    )
