"""Manzil bo'yicha filtrlash.

O'zbekchada apostrof bir necha xil yoziladi va "viloyati"/"tumani"
qo'shimchalari bor — shuning uchun solishtirish oddiy tenglik emas.
"""

from __future__ import annotations

from sqlalchemy import (
    func,
    or_,
)

from app.public_discovery.queries.constants import (
    _LOCATION_APOSTROPHES,
    _LOCATION_SUFFIXES,
)
from app.public_discovery.queries.helpers import (
    _contains,
)
from app.public_discovery.schemas import (
    PublicSearchParams,
)


def _location_key(value: str) -> str:
    key = " ".join(str(value or "").casefold().strip().split())
    for apostrophe in _LOCATION_APOSTROPHES:
        key = key.replace(apostrophe, "'")
    for suffix in _LOCATION_SUFFIXES:
        if key.endswith(suffix):
            key = key[: -len(suffix)].rstrip()
            break
    return key


def _location_contains(column, value: str):
    """Eski va yangi o'zbekcha apostrof yozuvlarini SQLda birga qidiradi."""
    key = _location_key(value)
    variants = {key}
    variants.update(
        key.replace("'", apostrophe) for apostrophe in _LOCATION_APOSTROPHES
    )
    return or_(
        *(
            func.lower(column).contains(variant)
            for variant in sorted(variants)
            if variant
        )
    )


def _location_constraints(
    region_column,
    district_column,
    mahalla_column,
    params: PublicSearchParams,
):
    constraints = []
    if params.region:
        region_match = _contains(region_column, params.region)
        if params.district:
            # V7 ko'chirishda ayrim eski profillarning tumani saqlangan,
            # ammo viloyati bo'sh qolgan. Tuman qat'iy mos bo'lsa, shu yozuvni
            # qidiruvdan yo'qotmaymiz; region mavjud yozuvlarda baribir tekshiriladi.
            region_match = or_(
                func.coalesce(func.trim(region_column), "") == "",
                region_match,
            )
        constraints.append(region_match)
    if params.district:
        constraints.append(_contains(district_column, params.district))
    if params.mahalla:
        constraints.append(_contains(mahalla_column, params.mahalla))
    return constraints
