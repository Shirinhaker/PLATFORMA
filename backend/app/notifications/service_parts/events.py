"""Hodisadan kelib chiqadigan bildirishnomalar."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account
from app.listings.model import Listing
from app.notifications.service_parts.base import NotificationServiceBase
from app.notifications.service_parts.helpers import (
    CATEGORY_NAMES,
)
from app.profiles.model import ProfileLink


class EventsMixin(NotificationServiceBase):
    async def notify_listing_published(
        self,
        session: AsyncSession,
        *,
        listing: Listing,
        now: int,
    ) -> int:
        if listing.visibility != "all" or listing.status != "active":
            return 0
        filters = await self._repository.filters_for_category(
            session, category=listing.category
        )
        if not filters:
            return 0
        owner_ids = {
            int(identifier)
            for identifier in (
                listing.owner_user_account_id,
                listing.owner_business_account_id,
            )
            if identifier is not None
        }
        if listing.owner_business_account_id is not None:
            linked_owner = await session.scalar(
                select(ProfileLink.user_account_id).where(
                    ProfileLink.business_account_id == listing.owner_business_account_id
                )
            )
            if linked_owner is not None:
                owner_ids.add(int(linked_owner))
        candidates = {
            int(row.account_id)
            for row in filters
            if int(row.account_id) not in owner_ids
            and self._matches_filter(row, listing)
        }
        if not candidates:
            return 0
        telegram_accounts = set(
            (
                await session.scalars(
                    select(Account.id).where(
                        Account.id.in_(candidates),
                        Account.telegram_user_id.is_not(None),
                    )
                )
            ).all()
        )
        notified: set[int] = set()
        for row in filters:
            account_id = int(row.account_id)
            if (
                account_id in notified
                or account_id not in telegram_accounts
                or account_id in owner_ids
                or not self._matches_filter(row, listing)
            ):
                continue
            await self._repository.append(
                session,
                account_id=account_id,
                account_type=row.account_type,
                row={
                    "event_key": f"listing:{listing.id}:filter",
                    "title": "Yangi mos e’lon",
                    "body": (
                        f"{CATEGORY_NAMES.get(listing.category, listing.category)}"
                        f" · {listing.title}"
                    ),
                    "listing_id": listing.id,
                    "listing_public_id": listing.public_id,
                    "action_type": "view_listing",
                    "requires_action": 0,
                    "is_read": 0,
                    "created_at": now,
                },
            )
            notified.add(account_id)
        return len(notified)
