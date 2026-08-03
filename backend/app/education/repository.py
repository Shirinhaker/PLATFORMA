from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.cabinet_records.repository import CabinetRecordRepository
from app.catalog.model import CatalogItem
from app.legacy_migration.model import LegacyIdMap, ReviewState
from app.profiles.model import BusinessProfile, UserProfile


class EducationEnrollmentRepository:
    def __init__(
        self,
        cabinet_records: CabinetRecordRepository | None = None,
    ) -> None:
        self._cabinet_records = cabinet_records or CabinetRecordRepository()

    async def user_profile(
        self,
        session: AsyncSession,
        account_id: int,
    ) -> UserProfile | None:
        return await session.get(UserProfile, account_id)

    async def locked_course_context(
        self,
        session: AsyncSession,
        public_id: str,
    ) -> tuple[CatalogItem, BusinessProfile] | None:
        statement = (
            select(CatalogItem, BusinessProfile)
            .join(
                BusinessProfile,
                BusinessProfile.account_id == CatalogItem.business_account_id,
            )
            .join(Account, Account.id == BusinessProfile.account_id)
            .where(
                CatalogItem.public_id == public_id,
                CatalogItem.kind == "service",
                CatalogItem.status == "active",
                CatalogItem.review_state == ReviewState.READY,
                BusinessProfile.direction == "Ta'lim faoliyati",
                Account.status == "active",
                Account.account_type == AccountType.BUSINESS,
            )
            .with_for_update(of=BusinessProfile)
            .limit(1)
        )
        row = (await session.execute(statement)).first()
        if row is None:
            return None
        return row[0], row[1]

    async def legacy_id(
        self,
        session: AsyncSession,
        entity_type: str,
        target_id: int,
    ) -> int | None:
        value = await session.scalar(
            select(LegacyIdMap.legacy_id)
            .where(
                LegacyIdMap.entity_type == entity_type,
                LegacyIdMap.target_id == target_id,
                LegacyIdMap.mapping_status == "mapped",
            )
            .order_by(LegacyIdMap.legacy_id)
            .limit(1)
        )
        return int(value) if value is not None else None

    async def resource_rows(
        self,
        session: AsyncSession,
        profile: BusinessProfile,
        resource: str,
    ) -> list[dict[str, Any]]:
        if await self._cabinet_records.has_resource(
            session,
            account_id=profile.account_id,
            account_type="business",
            resource=resource,
        ):
            rows = await self._cabinet_records.read_resource(
                session,
                account_id=profile.account_id,
                account_type="business",
                resource=resource,
            )
            return [dict(row) for row in rows if isinstance(row, dict)]
        payload = (
            profile.cabinet_payload
            if isinstance(profile.cabinet_payload, dict)
            else {}
        )
        rows = payload.get(resource, [])
        if not isinstance(rows, list):
            return []
        return [dict(row) for row in rows if isinstance(row, dict)]

    async def replace_resource(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        resource: str,
        rows: list[dict[str, Any]],
    ) -> None:
        await self._cabinet_records.replace_resource(
            session,
            account_id=account_id,
            account_type="business",
            resource=resource,
            rows=rows,
        )
