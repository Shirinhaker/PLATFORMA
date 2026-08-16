from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.core.errors import ApiError
from app.listings.model import Listing
from app.notifications.model import NotificationFilter
from app.notifications.repository import NotificationRepository
from app.notifications.schemas import (
    ActionNotificationListRead,
    NotificationFilterRead,
    NotificationFilterWrite,
    NotificationListRead,
    NotificationMutationRead,
    NotificationPreferenceRead,
    NotificationPreferenceWrite,
    NotificationRead,
    PushDeviceRead,
    PushDeviceRemove,
    PushDeviceWrite,
    PushStatusRead,
)
from app.profiles.model import ProfileLink

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NowProvider = Callable[[], datetime]
PRICE_RE = re.compile(r"[\d][\d\s]*")
CATEGORY_NAMES = {
    "uy": "Uy-joy",
    "ish": "Ish o‘rinlari",
    "moshina": "Moshinalar",
    "hayvon": "Hayvonlar",
    "texnika": "Texnika",
    "boshqa": "Boshqalar",
}


def price_number(value: str) -> int | None:
    text = value.casefold().replace("\u00a0", " ")
    match = PRICE_RE.search(text)
    if match is None:
        return None
    number = int(re.sub(r"\s", "", match.group(0)) or 0)
    if not number:
        return None
    if "mln" in text or "million" in text:
        number *= 1_000_000
    elif "ming" in text:
        number *= 1_000
    return number


class NotificationService:
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

    async def list(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        staff_id: int | None = None,
        permissions: tuple[str, ...] = (),
    ) -> NotificationListRead:
        async with self._session_factory() as session:
            rows = await self._repository.list_rows(
                session,
                account_id=account_id,
                account_type=account_type.value,
            ) or []
            visible = [
                row for row in rows
                if self._visible(row, staff_id=staff_id, permissions=permissions)
            ]
            unread = sum(
                1 for row in visible
                if not int(row.get("is_read") or 0)
                and not int(row.get("resolved_at") or 0)
            )
            return NotificationListRead(
                items=[self._read(row) for row in visible],
                unread=unread,
            )

    async def actions(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        staff_id: int | None = None,
        permissions: tuple[str, ...] = (),
    ) -> ActionNotificationListRead:
        async with self._session_factory() as session:
            rows = await self._repository.actionable_rows(
                session,
                account_id=account_id,
                account_type=account_type.value,
            )
            visible = [
                row for row in rows
                if self._visible(row, staff_id=staff_id, permissions=permissions)
            ]
            return ActionNotificationListRead(
                items=[self._read(row) for row in visible],
                count=len(visible),
            )

    async def mark_read(
        self,
        *,
        notification_id: int,
        account_id: int,
        account_type: AccountType,
        staff_id: int | None = None,
        permissions: tuple[str, ...] = (),
    ) -> NotificationMutationRead:
        async with self._session_factory() as session:
            row = await self._repository.get_row(
                session,
                account_id=account_id,
                account_type=account_type.value,
                notification_id=notification_id,
            )
            if row is None or not self._visible(
                row, staff_id=staff_id, permissions=permissions
            ):
                raise ApiError(
                    404,
                    "notification_not_found",
                    "Bildirishnoma topilmadi.",
                )
            now = self._now()
            await self._repository.mark_read(
                session,
                account_id=account_id,
                account_type=account_type.value,
                notification_id=notification_id,
                read_at=now,
                resolve=str(row.get("action_type") or "") == "view_ready",
            )
            await session.commit()
            return NotificationMutationRead(read_at=now)

    async def mark_all_read(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        staff_id: int | None = None,
        permissions: tuple[str, ...] = (),
    ) -> NotificationMutationRead:
        async with self._session_factory() as session:
            now = self._now()
            if staff_id is None:
                await self._repository.mark_all_read(
                    session,
                    account_id=account_id,
                    account_type=account_type.value,
                    read_at=now,
                )
            else:
                rows = await self._repository.list_rows(
                    session,
                    account_id=account_id,
                    account_type=account_type.value,
                ) or []
                ids = [
                    int(row["id"])
                    for row in rows
                    if not int(row.get("is_read") or 0)
                    and self._visible(
                        row, staff_id=staff_id, permissions=permissions
                    )
                ]
                await self._repository.mark_ids_read(
                    session,
                    account_id=account_id,
                    account_type=account_type.value,
                    notification_ids=ids,
                    read_at=now,
                )
            await session.commit()
            return NotificationMutationRead(read_at=now)

    async def preference(
        self,
        *,
        account_id: int,
        account_type: AccountType,
    ) -> NotificationPreferenceRead:
        async with self._session_factory() as session:
            row = await self._repository.preference(
                session,
                account_id=account_id,
                account_type=account_type.value,
            )
            if row is None:
                return NotificationPreferenceRead()
            return NotificationPreferenceRead(
                enabled=bool(row.enabled),
                orders_enabled=bool(row.orders_enabled),
            )

    async def save_preference(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: NotificationPreferenceWrite,
    ) -> NotificationPreferenceRead:
        async with self._session_factory() as session:
            await self._repository.save_preference(
                session,
                account_id=account_id,
                account_type=account_type.value,
                enabled=body.enabled,
                orders_enabled=body.orders_enabled,
                updated_at=self._now(),
            )
            await session.commit()
            return NotificationPreferenceRead(**body.model_dump())

    async def filters(
        self,
        *,
        account_id: int,
        account_type: AccountType,
    ) -> list[NotificationFilterRead]:
        async with self._session_factory() as session:
            rows = await self._repository.filters(
                session,
                account_id=account_id,
                account_type=account_type.value,
            )
            return [self._filter_read(row) for row in rows]

    async def add_filter(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: NotificationFilterWrite,
    ) -> NotificationFilterRead:
        async with self._session_factory() as session:
            row = await self._repository.add_filter(
                session,
                account_id=account_id,
                account_type=account_type.value,
                category=body.cat,
                region=body.region,
                district=body.district,
                price_min=body.price_min,
                price_max=body.price_max,
                keyword=body.keyword,
                created_at=self._now(),
            )
            await session.commit()
            return self._filter_read(row)

    async def remove_filter(
        self,
        *,
        filter_id: int,
        account_id: int,
        account_type: AccountType,
    ) -> NotificationMutationRead:
        async with self._session_factory() as session:
            removed = await self._repository.remove_filter(
                session,
                account_id=account_id,
                account_type=account_type.value,
                filter_id=filter_id,
            )
            if not removed:
                raise ApiError(
                    404,
                    "notification_filter_not_found",
                    "Filtr topilmadi.",
                )
            await session.commit()
            return NotificationMutationRead()

    async def register_device(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: PushDeviceWrite,
    ) -> PushDeviceRead:
        async with self._session_factory() as session:
            owner_id = await self._device_owner_id(
                session, account_id=account_id, account_type=account_type
            )
            device_id = await self._repository.register_device(
                session,
                account_id=owner_id,
                token=body.token,
                platform=body.platform,
                device_name=body.device_name,
                app_version=body.app_version,
                now=self._now(),
            )
            await session.commit()
            return PushDeviceRead(device_id=device_id)

    async def unregister_device(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: PushDeviceRemove,
    ) -> NotificationMutationRead:
        async with self._session_factory() as session:
            owner_id = await self._device_owner_id(
                session, account_id=account_id, account_type=account_type
            )
            await self._repository.unregister_device(
                session,
                account_id=owner_id,
                token=body.token,
                now=self._now(),
            )
            await session.commit()
            return NotificationMutationRead()

    async def push_status(
        self,
        *,
        account_id: int,
        account_type: AccountType,
    ) -> PushStatusRead:
        async with self._session_factory() as session:
            owner_id = await self._device_owner_id(
                session, account_id=account_id, account_type=account_type
            )
            active, pending = await self._repository.push_status(
                session, account_id=owner_id
            )
            return PushStatusRead(
                configured=self._push_configured,
                active_devices=active,
                pending=pending,
            )

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
                    ProfileLink.business_account_id
                    == listing.owner_business_account_id
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
        telegram_accounts = set((await session.scalars(
            select(Account.id).where(
                Account.id.in_(candidates),
                Account.telegram_user_id.is_not(None),
            )
        )).all())
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
        haystack = " ".join((
            listing.title,
            listing.description,
            listing.address,
        )).casefold()
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
