"""Kabinet payloadida maxfiy qiymat qolmaganini tekshirish."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.legacy_migration.model import (
    LegacyIdMap,
)
from app.legacy_migration.verify_parts.helpers import (
    _is_explicit_demo,
    _is_sensitive_key,
)
from app.profiles.model import BusinessProfile, UserProfile


async def _cabinet_payload_violations(
    session: AsyncSession,
    run_id: int,
) -> tuple[int, int]:
    mappings = (
        await session.scalars(
            select(LegacyIdMap).where(
                LegacyIdMap.entity_type.in_(("user_account", "business_account")),
                LegacyIdMap.last_run_id == run_id,
                LegacyIdMap.target_id.is_not(None),
            )
        )
    ).all()
    user_ids = {
        int(mapping.target_id)
        for mapping in mappings
        if mapping.entity_type == "user_account" and mapping.target_id is not None
    }
    business_ids = {
        int(mapping.target_id)
        for mapping in mappings
        if mapping.entity_type == "business_account" and mapping.target_id is not None
    }

    payloads: list[object] = []
    if user_ids:
        payloads.extend(
            profile.cabinet_payload
            for profile in (
                await session.scalars(
                    select(UserProfile).where(UserProfile.account_id.in_(user_ids))
                )
            ).all()
        )
    if business_ids:
        payloads.extend(
            profile.cabinet_payload
            for profile in (
                await session.scalars(
                    select(BusinessProfile).where(
                        BusinessProfile.account_id.in_(business_ids)
                    )
                )
            ).all()
        )

    demo_rows = 0
    sensitive_fields = 0
    for payload in payloads:
        found_demo, found_sensitive = _inspect_cabinet_value(payload)
        demo_rows += found_demo
        sensitive_fields += found_sensitive
    return demo_rows, sensitive_fields


def _inspect_cabinet_value(
    value: object,
    *,
    subscription_activation: bool = False,
) -> tuple[int, int]:
    if isinstance(value, dict):
        demo_rows = int(
            _is_explicit_demo(
                value,
                ignored_flags=(
                    frozenset({"is_demo"}) if subscription_activation else frozenset()
                ),
            )
        )
        sensitive_fields = 0
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                sensitive_fields += 1
                continue
            child_demo, child_sensitive = _inspect_cabinet_value(
                item,
                subscription_activation=(str(key) == "business_subscriptions"),
            )
            demo_rows += child_demo
            sensitive_fields += child_sensitive
        return demo_rows, sensitive_fields
    if isinstance(value, (list, tuple)):
        demo_rows = 0
        sensitive_fields = 0
        for item in value:
            child_demo, child_sensitive = _inspect_cabinet_value(
                item,
                subscription_activation=subscription_activation,
            )
            demo_rows += child_demo
            sensitive_fields += child_sensitive
        return demo_rows, sensitive_fields
    return 0, 0
