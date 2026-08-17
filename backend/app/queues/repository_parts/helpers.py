"""Navbat sanoqlari — jadval bo'yicha oddiy hisoblar."""

from __future__ import annotations

from sqlalchemy import func, select

from app.catalog.model import CatalogItem
from app.queues.model import (
    QueueEntry,
    QueueProvider,
    QueueProviderService,
)

ACTIVE_STATUSES = ("waiting", "called", "in_service")


def active_provider_count(catalog_item_id, business_account_id):
    return (
        select(func.count(QueueProviderService.id))
        .select_from(QueueProviderService)
        .join(
            QueueProvider,
            QueueProvider.id == QueueProviderService.provider_id,
        )
        .where(
            QueueProviderService.catalog_item_id == catalog_item_id,
            QueueProviderService.active.is_(True),
            QueueProvider.business_account_id == business_account_id,
            QueueProvider.status == "active",
        )
        .correlate(CatalogItem)
        .scalar_subquery()
    )


def active_queue_count(catalog_item_id, business_account_id, queue_date):
    return (
        select(func.count(QueueEntry.id))
        .where(
            QueueEntry.business_account_id == business_account_id,
            QueueEntry.catalog_item_id == catalog_item_id,
            QueueEntry.queue_date == queue_date,
            QueueEntry.status.in_(ACTIVE_STATUSES),
        )
        .correlate(CatalogItem)
        .scalar_subquery()
    )
