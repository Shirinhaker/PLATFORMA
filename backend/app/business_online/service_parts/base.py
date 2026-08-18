"""Umumiy asos: bogliqliklar, resurs oqish, saqlash, kesh."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.business_online.payload.helpers import normalized_payload
from app.business_online.payload.spec import resource_rows
from app.business_online.service_parts.helpers import (
    RELATIONAL_EDUCATION_RESOURCES,
    CatalogSync,
    InventorySync,
    ListingSync,
    SessionFactory,
)
from app.cabinet_records.repository import CabinetRecordRepository
from app.catalog.cache_epoch import CatalogCacheEpoch
from app.catalog.live_sync import CATALOG_RESOURCES, sync_business_catalog
from app.education.cabinet import EducationCabinetService
from app.education.repository import (
    EducationEnrollmentRepository,
)
from app.education.service import EducationEnrollmentService
from app.inventory.live_sync import sync_business_inventory
from app.listings.live_sync import LISTING_RESOURCES, sync_business_listings
from app.notifications.repository_parts import NotificationRepository
from app.profiles.model import BusinessProfile


class BusinessOnlineServiceBase:
    def __init__(
        self,
        session_factory: SessionFactory,
        repository: CabinetRecordRepository | None = None,
        *,
        catalog_sync: CatalogSync = sync_business_catalog,
        listing_sync: ListingSync = sync_business_listings,
        inventory_sync: InventorySync = sync_business_inventory,
        catalog_cache_epoch: CatalogCacheEpoch | None = None,
        notification_repository: NotificationRepository | None = None,
        education_repository: EducationEnrollmentRepository | None = None,
        education_service: EducationEnrollmentService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or CabinetRecordRepository()
        self._catalog_sync = catalog_sync
        self._listing_sync = listing_sync
        self._inventory_sync = inventory_sync
        self._catalog_cache_epoch = catalog_cache_epoch
        self._notifications = notification_repository or NotificationRepository()
        self._education = education_repository or EducationEnrollmentRepository()
        self._education_service = education_service or EducationEnrollmentService(
            session_factory,
            repository=self._education,
        )
        self._education_cabinet = EducationCabinetService(
            repository=self._education,
        )

    async def _resource_rows(
        self,
        session: AsyncSession,
        *,
        profile: BusinessProfile,
        account_id: int,
        resource: str,
    ) -> list[Any]:
        if await self._repository.has_resource(
            session,
            account_id=account_id,
            account_type="business",
            resource=resource,
        ):
            return await self._repository.read_resource(
                session,
                account_id=account_id,
                account_type="business",
                resource=resource,
            )
        return resource_rows(profile.cabinet_payload, resource)

    async def _hybrid_payload(
        self,
        session: AsyncSession,
        profile: BusinessProfile,
    ) -> dict[str, Any]:
        payload = normalized_payload(profile.cabinet_payload)
        relational = await self._repository.read_payload(
            session,
            account_id=profile.account_id,
            account_type="business",
        )
        payload.update(relational)
        # Ta'lim resurslari o'z jadvallariga ko'chirilgan — ular JSON
        # nusxasidan emas, jadvaldan o'qiladi.
        if self._education.supported(session):
            for resource in RELATIONAL_EDUCATION_RESOURCES:
                rows = await self._education.list_rows(
                    session,
                    business_account_id=profile.account_id,
                    resource=resource,
                )
                if rows is not None:
                    payload[resource] = rows
        return payload

    async def _persist_resources(
        self,
        session: AsyncSession,
        account_id: int,
        owner_name: str,
        payload: dict[str, Any],
        resources: set[str],
    ) -> bool:
        for resource in sorted(resources):
            await self._repository.replace_resource(
                session,
                account_id=account_id,
                account_type="business",
                resource=resource,
                rows=resource_rows(payload, resource),
            )
        catalog_changed = bool(CATALOG_RESOURCES.intersection(resources))
        if catalog_changed:
            await self._catalog_sync(
                session,
                account_id=account_id,
                owner_name=owner_name,
                payload=payload,
                changed_resources=resources,
            )
            await self._inventory_sync(
                session,
                account_id=account_id,
                payload=payload,
                changed_resources=resources,
            )
        listings_changed = bool(LISTING_RESOURCES.intersection(resources))
        if listings_changed:
            await self._listing_sync(
                session,
                account_id=account_id,
                payload=payload,
                changed_resources=resources,
            )
        return catalog_changed or listings_changed

    async def _invalidate_catalog_cache(self, changed: bool) -> None:
        if changed and self._catalog_cache_epoch is not None:
            await self._catalog_cache_epoch.bump()
