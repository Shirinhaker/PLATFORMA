"""Navbatga yozilish: onlayn va kabinet orqali."""

from __future__ import annotations

from datetime import date, time

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import AccountType
from app.catalog.model import CatalogItem
from app.core.errors import ApiError
from app.profiles.model import BusinessProfile
from app.queues.model import QueueEntry
from app.queues.schemas import (
    QueueCreate,
    QueueEntryRead,
    QueueOfflineCreate,
)
from app.queues.service_parts.base import QueueServiceBase
from app.queues.service_parts.helpers import (
    _clock,
    _clock_text,
    _generated_slots,
    _medical_code,
    _slot_minutes,
)


class BookingMixin(QueueServiceBase):
    async def create_online(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: QueueCreate,
    ) -> QueueEntryRead:
        if account_type is not AccountType.USER:
            raise ApiError(403, "queue_user_required", "Avval oddiy profilga o'ting.")
        async with self._session_factory() as session:
            customer = await self._repository.user(session, account_id)
            if customer is None:
                raise ApiError(404, "queue_customer_not_found", "Profil topilmadi.")
            business, item = await self._public_context(
                session, body.business_public_id, body.item_public_id
            )
            entry = await self._create_entry(
                session,
                business=business,
                item=item,
                provider_id=body.provider_id,
                queue_date=body.queue_date,
                slot_text=body.slot_time,
                customer_account_id=account_id,
                patient_name=customer.name or "Bemor",
                phone=customer.phone or "",
                note=body.note,
                source="online",
                enforce_schedule=True,
            )
            booked = (
                f"{entry.queue_code} navbat {entry.queue_date.isoformat()} sanasiga"
                + (
                    f" soat {_clock_text(entry.slot_time)} ga"
                    if entry.slot_time
                    else ""
                )
                + " saqlandi."
            )
            await self._notify(
                session,
                entry,
                event="booked",
                title="Navbat olindi",
                body=booked,
                action_type="medical_queue_booked",
            )
            await session.commit()
            return await self._project(session, entry.id)

    async def create_offline(
        self,
        *,
        business_account_id: int,
        body: QueueOfflineCreate,
    ) -> QueueEntryRead:
        async with self._session_factory() as session:
            business = await self._business(session, business_account_id)
            item = await self._enabled_item(
                session, business_account_id, body.item_public_id
            )
            entry = await self._create_entry(
                session,
                business=business,
                item=item,
                provider_id=body.provider_id,
                queue_date=body.queue_date,
                slot_text=body.slot_time,
                customer_account_id=None,
                patient_name=body.patient_name,
                phone=body.phone,
                note=body.note,
                source="offline",
                enforce_schedule=False,
            )
            await session.commit()
            return await self._project(session, entry.id)

    async def _create_entry(
        self,
        session: AsyncSession,
        *,
        business: BusinessProfile,
        item: CatalogItem,
        provider_id: int,
        queue_date: date,
        slot_text: str,
        customer_account_id: int | None,
        patient_name: str,
        phone: str,
        note: str,
        source: str,
        enforce_schedule: bool,
    ) -> QueueEntry:
        self._validate_date(queue_date)
        provider = await self._provider_context(session, business, item, provider_id)
        if enforce_schedule and not self._works_on(provider, queue_date):
            raise ApiError(
                400,
                "queue_provider_day_off",
                "Bu kunda xizmat ko'rsatuvchi ishlamaydi.",
            )
        now = self._now()
        slot_value: time | None = None
        if provider.mode == "slot":
            if not slot_text:
                raise ApiError(400, "queue_slot_required", "Qabul vaqtini tanlang.")
            slot_value = _clock(slot_text)
            if slot_value not in _generated_slots(
                provider.work_start, provider.work_end, provider.avg_minutes
            ):
                raise ApiError(
                    400,
                    "queue_slot_outside_schedule",
                    "Bu vaqt qabul jadvalida yo'q.",
                )
            local_now = self._local_now()
            if (
                enforce_schedule
                and queue_date == local_now.date()
                and (
                    _slot_minutes(slot_value) <= local_now.hour * 60 + local_now.minute
                )
            ):
                raise ApiError(
                    400,
                    "queue_slot_in_past",
                    "Bu vaqt allaqachon o'tib ketgan.",
                )
            if (
                customer_account_id is not None
                and await self._repository.active_customer_duplicate(
                    session,
                    business_account_id=business.account_id,
                    catalog_item_id=item.id,
                    provider_id=provider.id,
                    queue_date=queue_date,
                    customer_account_id=customer_account_id,
                    slot_time=slot_value,
                )
            ):
                raise ApiError(
                    400,
                    "queue_duplicate",
                    "Bu vaqtga allaqachon yozilgansiz.",
                )
            if await self._repository.slot_taken(
                session,
                business_account_id=business.account_id,
                catalog_item_id=item.id,
                provider_id=provider.id,
                queue_date=queue_date,
                slot_time=slot_value,
            ):
                raise ApiError(
                    409,
                    "queue_slot_taken",
                    "Bu vaqt band qilindi. Boshqa vaqt tanlang.",
                )
            queue_no = _slot_minutes(slot_value)
            queue_code = f"{_medical_code(item.name)}-{slot_value.strftime('%H%M')}"
        else:
            if (
                customer_account_id is not None
                and await self._repository.active_customer_duplicate(
                    session,
                    business_account_id=business.account_id,
                    catalog_item_id=item.id,
                    provider_id=provider.id,
                    queue_date=queue_date,
                    customer_account_id=customer_account_id,
                    slot_time=None,
                )
            ):
                raise ApiError(
                    400,
                    "queue_duplicate",
                    "Bu xizmatga ushbu kunga allaqachon navbatingiz bor.",
                )
            queue_no = await self._repository.allocate_live_number(
                session,
                business_account_id=business.account_id,
                catalog_item_id=item.id,
                provider_id=provider.id,
                queue_date=queue_date,
                now=now,
            )
            queue_code = f"{_medical_code(item.name)}-{queue_no:03d}"

        entry = QueueEntry(
            business_account_id=business.account_id,
            legacy_source_id=None,
            catalog_item_id=item.id,
            provider_id=provider.id,
            customer_account_id=customer_account_id,
            patient_name=patient_name[:120],
            phone=phone[:32],
            service_name_snapshot=item.name[:160],
            provider_name_snapshot=provider.staff_name_snapshot[:120],
            queue_date=queue_date,
            queue_no=queue_no,
            queue_code=queue_code,
            source=source,
            status="waiting",
            note=note[:200],
            slot_time=slot_value,
            created_at=now,
            updated_at=now,
        )
        try:
            await self._repository.add_entry(session, entry)
        except IntegrityError as exc:
            await session.rollback()
            if slot_value is not None:
                raise ApiError(
                    409,
                    "queue_slot_taken",
                    "Bu vaqt band qilindi. Boshqa vaqt tanlang.",
                ) from exc
            raise ApiError(
                400,
                "queue_duplicate",
                "Bu xizmatga ushbu kunga allaqachon navbatingiz bor.",
            ) from exc
        return entry
