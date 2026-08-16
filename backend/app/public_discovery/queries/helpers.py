"""Ommaviy ID qurish va mayda SQL yordamchilari."""

from __future__ import annotations

from sqlalchemy import (
    String,
    func,
    literal,
)

from app.public_discovery.schemas import (
    PublicResultKind,
)
from app.public_ids import (
    build_listing_public_id as _build_listing_public_id,
)
from app.public_ids import (
    build_profile_public_id,
)


def _bounded_integer(value: object, maximum: int) -> int:
    try:
        return max(0, min(maximum, int(value or 0)))
    except (TypeError, ValueError):
        return 0


def build_public_id(kind: PublicResultKind, account_id: int) -> str:
    return build_profile_public_id(kind.value, account_id)


def build_listing_public_id(listing_id: int) -> str:
    return _build_listing_public_id(listing_id)


def _empty(label: str):
    return literal("").cast(String).label(label)


def _contains(column, value: str):
    return func.lower(column).contains(value.casefold())
