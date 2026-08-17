"""Umumiy asos: korinish, oqilganlik, filtr moslashuvi."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import AccountType
from app.listings.model import Listing
from app.notifications.model import NotificationFilter
from app.notifications.repository import NotificationRepository
from app.notifications.schemas import (
    NotificationFilterRead,
    NotificationRead,
)
from app.notifications.service_parts.helpers import (
    NowProvider,
    SessionFactory,
    price_number,
)
from app.profiles.model import ProfileLink


class NotificationServiceBase:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: NotificationRepository | None = None,
        now_provider: NowProvider | None = None,
        push_configured: bool = False,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or NotificationRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._push_configured = push_configured

    def _now(self) -> int:
        return int(self._now_provider().timestamp())

    async def _device_owner_id(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        account_type: AccountType,
    ) -> int:
        if account_type is not AccountType.BUSINESS:
            return account_id
        linked = await session.scalar(
            select(ProfileLink.user_account_id).where(
                ProfileLink.business_account_id == account_id
            )
        )
        return int(linked) if linked is not None else account_id

    @staticmethod
    def _visible(
        row: dict,
        *,
        staff_id: int | None,
        permissions: tuple[str, ...],
    ) -> bool:
        if staff_id is None:
            return True
        target_staff_id = int(row.get("target_staff_id") or 0)
        target_permission = str(row.get("target_permission") or "")
        if target_staff_id:
            return target_staff_id == staff_id
        if target_permission:
            return target_permission in permissions
        return "notifications" in permissions

    @staticmethod
    def _read(row: dict) -> NotificationRead:
        return NotificationRead(
            id=int(row["id"]),
            title=str(row.get("title") or ""),
            body=str(row.get("body") or ""),
            order_id=int(row.get("order_id") or 0) or None,
            listing_id=int(row.get("listing_id") or 0) or None,
            listing_public_id=str(row.get("listing_public_id") or ""),
            profile_kind=(
                str(row.get("profile_kind"))
                if row.get("profile_kind") in {"user", "business"}
                else None
            ),
            profile_public_id=str(row.get("profile_public_id") or ""),
            dining_order_id=int(row.get("dining_order_id") or 0) or None,
            medical_queue_id=int(row.get("medical_queue_id") or 0) or None,
            ride_id=int(row.get("ride_id") or 0) or None,
            action_type=str(row.get("action_type") or ""),
            requires_action=bool(row.get("requires_action")),
            is_read=bool(row.get("is_read")),
            created_at=int(row.get("created_at") or 0),
            read_at=int(row.get("read_at") or 0) or None,
            resolved_at=int(row.get("resolved_at") or 0) or None,
        )

    @staticmethod
    def _filter_read(row: NotificationFilter) -> NotificationFilterRead:
        return NotificationFilterRead(
            id=int(row.id),
            cat=row.category,
            region=row.region,
            district=row.district,
            price_min=int(row.price_min),
            price_max=int(row.price_max),
            keyword=row.keyword,
            created_at=int(row.created_at),
        )

    @staticmethod
    def _matches_filter(row: NotificationFilter, listing: Listing) -> bool:
        haystack = " ".join(
            (
                listing.title,
                listing.description,
                listing.address,
            )
        ).casefold()
        if row.region and row.region.casefold() not in haystack:
            return False
        if row.district and row.district.casefold() not in haystack:
            return False
        price = price_number(listing.price_text)
        if row.price_min and (price is None or price < row.price_min):
            return False
        if row.price_max and (price is None or price > row.price_max):
            return False
        if row.keyword and row.keyword.casefold() not in haystack:
            return False
        return True
