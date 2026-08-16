"""Faol obunani aniqlash.

Eski v1656 obunalari boshqacha yozilgan, shuning uchun ikki xil
tekshiruv bor.
"""

from __future__ import annotations

import time

from sqlalchemy import (
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.payments.model import BusinessSubscription
from app.profiles.model import BusinessProfile


def _has_legacy_active_subscription(
    profile: BusinessProfile,
    eligible_plan_codes: frozenset[str],
) -> bool:
    payload = (
        profile.cabinet_payload if isinstance(profile.cabinet_payload, dict) else {}
    )
    rows = payload.get("business_subscriptions", [])
    if not isinstance(rows, list):
        return False
    now = int(time.time())
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            expires_at = int(row.get("expires_at") or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if (
            str(row.get("status") or "") == "active"
            and str(row.get("plan_code") or "") in eligible_plan_codes
            and expires_at > now
        ):
            return True
    return False


async def _active_subscription_business_ids(
    session: AsyncSession,
    account_ids: set[int],
    eligible_plan_codes: frozenset[str],
) -> set[int]:
    """Faol Plus/Pro bizneslarni yangi jadvaldan bir so'rovda oladi."""
    if not account_ids or not eligible_plan_codes:
        return set()
    rows = await session.scalars(
        select(BusinessSubscription.business_account_id)
        .where(
            BusinessSubscription.business_account_id.in_(account_ids),
            BusinessSubscription.plan_code.in_(sorted(eligible_plan_codes)),
            BusinessSubscription.status == "active",
            BusinessSubscription.expires_at > int(time.time()),
        )
        .distinct()
    )
    return {int(account_id) for account_id in rows.all()}


async def _active_pro_business_ids(
    session: AsyncSession,
    account_ids: set[int],
) -> set[int]:
    """Xarita v1656 qoidasi: faol Pro bizneslar."""
    return await _active_subscription_business_ids(
        session,
        account_ids,
        frozenset({"pro"}),
    )


async def _active_home_offer_business_ids(
    session: AsyncSession,
    account_ids: set[int],
) -> set[int]:
    """Tuman kartalari v1656 qoidasi: Plus va Pro teng huquqli."""
    return await _active_subscription_business_ids(
        session,
        account_ids,
        frozenset({"plus", "pro"}),
    )


def _has_active_subscription(
    profile: BusinessProfile,
    active_business_ids: set[int],
    eligible_plan_codes: frozenset[str],
) -> bool:
    return profile.account_id in active_business_ids or _has_legacy_active_subscription(
        profile, eligible_plan_codes
    )
