from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, date, datetime, time, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import AccountType
from app.cabinet_records.repository import CabinetRecordRepository
from app.catalog.model import CatalogItem
from app.core.errors import ApiError
from app.notifications.repository import NotificationRepository
from app.profiles.model import BusinessProfile
from app.public_ids import build_content_public_id
from app.queues.model import QueueEntry, QueueProvider
from app.queues.repository import ACTIVE_STATUSES, QueueRepository
from app.queues.schemas import (
    QueueBusinessSetupRead,
    QueueCreate,
    QueueEntryRead,
    QueueOfflineCreate,
    QueueNotificationRead,
    QueueOptionsRead,
    QueueProviderRead,
    QueueProviderWrite,
    QueueServiceRead,
    QueueSlotsRead,
    QueueStaffRead,
    QueueStatusChange,
    QueueSwap,
)


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NowProvider = Callable[[], datetime]
UZBEKISTAN_TZ = timezone(timedelta(hours=5))
QUEUE_DIRECTIONS = frozenset({
    "Transport va logistika",
    "Xizmat ko'rsatish",
    "Maishiy xizmatlar",
    "Qurilish",
    "Tibbiy xizmatlar",
    "Ko'chmas mulk",
    "Axborot texnologiyalari",
    "Konsalting va professional",
    "Madaniyat, sport, ko'ngilochar",
    "Turizm va mehmonxona",
    "Reklama va marketing",
    "Poligrafiya va nashriyot",
    "Moliyaviy faoliyat",
    "Import-eksport",
})
TERMINAL_STATUSES = frozenset({"done", "cancelled", "no_show"})


def _clock(value: str) -> time:
    return time.fromisoformat(value)


def _clock_text(value: time | None) -> str:
    return value.strftime("%H:%M") if value is not None else ""


def _medical_code(name: str) -> str:
    letters = "".join(character for character in str(name or "").upper() if character.isalnum())[:3]
    return letters or "NAV"


def _slot_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _generated_slots(start: time, end: time, step: int) -> list[time]:
    first = _slot_minutes(start)
    last = _slot_minutes(end)
    interval = max(5, int(step or 20))
    if first >= last:
        return []
    values: list[time] = []
    current = first
    while current + interval <= last:
        values.append(time(current // 60, current % 60))
        current += interval
    return values


class QueueService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: QueueRepository | None = None,
        cabinet_repository: CabinetRecordRepository | None = None,
        notification_repository: NotificationRepository | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or QueueRepository()
        self._cabinet_repository = cabinet_repository or CabinetRecordRepository()
        self._notifications = notification_repository or NotificationRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def business_setup(self, *, business_account_id: int) -> QueueBusinessSetupRead:
        async with self._session_factory() as session:
            business = await self._business(session, business_account_id)
            services = await self._repository.enabled_items(
                session,
                business_account_id=business_account_id,
            )
            staff = await self._staff_rows(session, business)
            await session.rollback()
            return QueueBusinessSetupRead(
                services=[
                    QueueServiceRead(
                        public_id=self._item_public_id(item),
                        name=item.name,
                        price_text=item.price_text,
                    )
                    for item in services
                ],
                staff=[
                    QueueStaffRead(
                        id=int(row["id"]),
                        name=str(row["name"]),
                        profession=str(row["profession"]),
                    )
                    for row in staff
                ],
            )

    async def list_providers(
        self,
        *,
        business_account_id: int,
    ) -> list[QueueProviderRead]:
        async with self._session_factory() as session:
            await self._business(session, business_account_id)
            providers = await self._repository.providers(
                session,
                business_account_id=business_account_id,
            )
            links = await self._repository.provider_links(
                session, [provider.id for provider in providers]
            )
            await session.rollback()
            return [
                self._provider_read(provider, links.get(provider.id, []))
                for provider in providers
            ]

    async def create_provider(
        self,
        *,
        business_account_id: int,
        body: QueueProviderWrite,
    ) -> QueueProviderRead:
        async with self._session_factory() as session:
            business = await self._business(session, business_account_id)
            if await self._repository.provider_by_staff(
                session,
                business_account_id=business_account_id,
                staff_id=body.staff_id,
            ) is not None:
                raise ApiError(
                    409,
                    "queue_provider_exists",
                    "Xizmat ko'rsatuvchi avval biriktirilgan.",
                )
            staff = await self._active_staff(session, business, body.staff_id)
            items = await self._provider_items(session, business_account_id, body)
            work_start, work_end = self._provider_times(body)
            now = self._now()
            provider = QueueProvider(
                business_account_id=business_account_id,
                legacy_source_id=None,
                legacy_staff_id=body.staff_id,
                staff_name_snapshot=str(staff["name"])[:120],
                profession_snapshot=str(staff["profession"])[:120],
                specialty=body.specialty,
                experience_years=body.experience_years,
                qualification=body.qualification,
                work_days=body.work_days,
                work_start=work_start,
                work_end=work_end,
                avg_minutes=body.avg_minutes,
                room=body.room,
                bio=body.bio,
                status=body.status,
                mode=body.mode,
                created_at=now,
                updated_at=now,
            )
            session.add(provider)
            await session.flush()
            await self._repository.replace_provider_links(
                session,
                provider=provider,
                items=items,
                now=now,
            )
            await session.commit()
            return self._provider_read(provider, items)

    async def update_provider(
        self,
        *,
        business_account_id: int,
        provider_id: int,
        body: QueueProviderWrite,
    ) -> QueueProviderRead:
        async with self._session_factory() as session:
            business = await self._business(session, business_account_id)
            provider = await self._repository.provider(
                session,
                provider_id=provider_id,
                business_account_id=business_account_id,
                lock=True,
            )
            if provider is None:
                raise ApiError(
                    404,
                    "queue_provider_not_found",
                    "Xizmat ko'rsatuvchi topilmadi.",
                )
            if body.staff_id != provider.legacy_staff_id:
                raise ApiError(
                    400,
                    "queue_provider_staff_immutable",
                    "Xizmat ko'rsatuvchi xodimini o'zgartirib bo'lmaydi.",
                )
            items = await self._provider_items(session, business_account_id, body)
            work_start, work_end = self._provider_times(body)
            provider.specialty = body.specialty
            provider.experience_years = body.experience_years
            provider.qualification = body.qualification
            provider.work_days = body.work_days
            provider.work_start = work_start
            provider.work_end = work_end
            provider.avg_minutes = body.avg_minutes
            provider.room = body.room
            provider.bio = body.bio
            provider.status = body.status
            provider.mode = body.mode
            provider.updated_at = self._now()
            await self._repository.replace_provider_links(
                session,
                provider=provider,
                items=items,
                now=provider.updated_at,
            )
            await session.commit()
            return self._provider_read(provider, items)

    async def options(
        self,
        *,
        business_public_id: str,
        item_public_id: str,
        queue_date: date | None,
    ) -> QueueOptionsRead:
        async with self._session_factory() as session:
            resolved_date = queue_date or self._local_now().date()
            business, item = await self._public_context(
                session, business_public_id, item_public_id
            )
            self._validate_date(resolved_date)
            rows = await self._repository.provider_options(
                session,
                business_account_id=business.account_id,
                catalog_item_id=item.id,
                queue_date=resolved_date,
            )
            links = await self._repository.provider_links(
                session, [provider.id for provider, _count in rows]
            )
            active_staff = await self._staff_rows(session, business)
            if await self._staff_source_exists(session, business):
                active_staff_ids = {int(row["id"]) for row in active_staff}
                rows = [
                    row
                    for row in rows
                    if row[0].legacy_staff_id in active_staff_ids
                ]
            response = QueueOptionsRead(
                business_public_id=business_public_id,
                item_public_id=item_public_id,
                queue_date=resolved_date,
                providers=[
                    self._provider_read(
                        provider,
                        links.get(provider.id, []),
                        queue_count=int(count or 0),
                    )
                    for provider, count in rows
                ],
            )
            await session.rollback()
            return response

    async def slots(
        self,
        *,
        business_public_id: str,
        item_public_id: str,
        provider_id: int,
        queue_date: date | None,
    ) -> QueueSlotsRead:
        async with self._session_factory() as session:
            resolved_date = queue_date or self._local_now().date()
            business, item = await self._public_context(
                session, business_public_id, item_public_id
            )
            provider = await self._provider_context(
                session, business, item, provider_id
            )
            self._validate_date(resolved_date)
            if provider.mode != "slot":
                await session.rollback()
                return QueueSlotsRead(mode="live", slots=[])
            if not self._works_on(provider, resolved_date):
                await session.rollback()
                return QueueSlotsRead(mode="slot", slots=[])
            taken = await self._repository.taken_slots(
                session,
                catalog_item_id=item.id,
                provider_id=provider.id,
                queue_date=resolved_date,
            )
            local_now = self._local_now()
            values = [
                value
                for value in _generated_slots(
                    provider.work_start,
                    provider.work_end,
                    provider.avg_minutes,
                )
                if value not in taken
                and not (
                    resolved_date == local_now.date()
                    and _slot_minutes(value)
                    <= local_now.hour * 60 + local_now.minute
                )
            ]
            await session.rollback()
            return QueueSlotsRead(
                mode="slot",
                slots=[_clock_text(value) for value in values],
            )

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
                + (f" soat {_clock_text(entry.slot_time)} ga" if entry.slot_time else "")
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

    async def list_business(
        self,
        *,
        business_account_id: int,
        queue_date: date | None,
    ) -> list[QueueEntryRead]:
        async with self._session_factory() as session:
            await self._business(session, business_account_id)
            rows = await self._repository.list_business(
                session,
                business_account_id=business_account_id,
                queue_date=queue_date or self._local_now().date(),
            )
            await session.rollback()
            return [self._entry_read(*row) for row in rows]

    async def list_mine(
        self,
        *,
        account_id: int,
        account_type: AccountType,
    ) -> list[QueueEntryRead]:
        if account_type is not AccountType.USER:
            raise ApiError(403, "queue_user_required", "Avval oddiy profilga o'ting.")
        async with self._session_factory() as session:
            rows = await self._repository.list_mine(
                session,
                customer_account_id=account_id,
            )
            await session.rollback()
            return [self._entry_read(*row) for row in rows]

    async def cancel_mine(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        queue_id: int,
    ) -> QueueEntryRead:
        if account_type is not AccountType.USER:
            raise ApiError(403, "queue_user_required", "Avval oddiy profilga o'ting.")
        async with self._session_factory() as session:
            entry = await self._repository.entry(
                session,
                queue_id=queue_id,
                customer_account_id=account_id,
                lock=True,
            )
            if entry is None:
                raise ApiError(404, "queue_not_found", "Navbat topilmadi.")
            if entry.status not in {"waiting", "called"}:
                raise ApiError(
                    400,
                    "queue_cancel_forbidden",
                    "Bu navbatni endi bekor qilib bo'lmaydi.",
                )
            old_status = entry.status
            entry.status = "cancelled"
            entry.updated_at = self._now()
            await self._repository.add_history(
                session,
                entry=entry,
                action="status",
                old_value=old_status,
                new_value="cancelled",
                actor_account_id=account_id,
                now=entry.updated_at,
            )
            await session.commit()
            return await self._project(session, entry.id)

    async def mark_notification_read(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        notification_id: int,
    ) -> QueueNotificationRead:
        if account_type is not AccountType.USER:
            raise ApiError(403, "queue_user_required", "Avval oddiy profilga o'ting.")
        async with self._session_factory() as session:
            row = await self._notifications.get_row(
                session,
                account_id=account_id,
                account_type=AccountType.USER.value,
                notification_id=notification_id,
            )
            try:
                queue_id = int((row or {}).get("medical_queue_id") or 0)
            except (TypeError, ValueError):
                queue_id = 0
            if row is None or queue_id < 1:
                raise ApiError(
                    404,
                    "queue_notification_not_found",
                    "Navbat bildirishnomasi topilmadi.",
                )
            entry = await self._repository.entry(
                session,
                queue_id=queue_id,
                customer_account_id=account_id,
            )
            if entry is None:
                raise ApiError(
                    404,
                    "queue_notification_not_found",
                    "Navbat bildirishnomasi topilmadi.",
                )
            await self._notifications.mark_read(
                session,
                account_id=account_id,
                account_type=AccountType.USER.value,
                notification_id=notification_id,
                read_at=int(self._now().timestamp()),
            )
            await session.commit()
            return QueueNotificationRead(
                id=notification_id,
                medical_queue_id=queue_id,
                is_read=True,
            )

    async def change_status(
        self,
        *,
        business_account_id: int,
        queue_id: int,
        body: QueueStatusChange,
    ) -> QueueEntryRead:
        async with self._session_factory() as session:
            business = await self._business(session, business_account_id)
            entry = await self._repository.entry(
                session,
                queue_id=queue_id,
                business_account_id=business_account_id,
                lock=True,
            )
            if entry is None:
                raise ApiError(404, "queue_not_found", "Navbat topilmadi.")
            if entry.status in TERMINAL_STATUSES and body.status in ACTIVE_STATUSES:
                raise ApiError(
                    400,
                    "completed_queue",
                    "Yakunlangan navbatni qayta faollashtirib bo'lmaydi.",
                )
            old_status = entry.status
            entry.status = body.status
            entry.updated_at = self._now()
            await self._repository.add_history(
                session,
                entry=entry,
                action="status",
                old_value=old_status,
                new_value=body.status,
                actor_account_id=business_account_id,
                now=entry.updated_at,
            )
            if body.status == "called":
                called_by = (
                    "shifokor"
                    if business.direction == "Tibbiy xizmatlar"
                    else "xizmat ko'rsatuvchi"
                )
                await self._notify(
                    session,
                    entry,
                    event="called",
                    title="Navbatingiz keldi",
                    body=(
                        f"{entry.queue_code} navbat {called_by} tomonidan chaqirildi."
                    ),
                    action_type="medical_queue_called",
                )
                next_entry = await self._repository.next_waiting(session, entry)
                if next_entry is not None:
                    await self._notify(
                        session,
                        next_entry,
                        event=f"soon:{entry.queue_no}",
                        title="Navbatingiz yaqinlashdi",
                        body=(
                            f"Tayyorlaning — {next_entry.queue_code} "
                            "navbatgacha 1 kishi qoldi."
                        ),
                        action_type="medical_queue_soon",
                    )
            elif body.status == "cancelled":
                await self._notify(
                    session,
                    entry,
                    event="cancelled",
                    title="Navbat bekor qilindi",
                    body=(
                        f"{entry.queue_code} navbat muassasa tomonidan bekor qilindi."
                    ),
                    action_type="medical_queue_cancelled",
                )
            await session.commit()
            return await self._project(session, entry.id)

    async def swap(
        self,
        *,
        business_account_id: int,
        queue_id: int,
        body: QueueSwap,
    ) -> QueueEntryRead:
        async with self._session_factory() as session:
            business = await self._business(session, business_account_id)
            rows = await self._repository.entries_for_swap(
                session,
                business_account_id=business_account_id,
                queue_ids=[queue_id, body.other_queue_id],
            )
            by_id = {entry.id: entry for entry in rows}
            first = by_id.get(queue_id)
            second = by_id.get(body.other_queue_id)
            same_queue = first is not None and second is not None and first.id != second.id and (
                first.queue_date,
                first.provider_id,
                first.catalog_item_id,
            ) == (
                second.queue_date,
                second.provider_id,
                second.catalog_item_id,
            )
            if not same_queue or first is None or second is None:
                provider_label = (
                    "shifokor"
                    if business.direction == "Tibbiy xizmatlar"
                    else "xizmat ko'rsatuvchi"
                )
                raise ApiError(
                    400,
                    "queue_swap_mismatch",
                    f"Faqat bir xil xizmat va {provider_label}ning ikkita navbati almashtiriladi.",
                )
            first_number = first.queue_no
            second_number = second.queue_no
            prefix = _medical_code(first.service_name_snapshot)
            now = self._now()

            # Unique queue-number indeksi buzilmasligi uchun v1656 kabi vaqtincha
            # -1 ishlatiladi; bloklar ID tartibida oldindan olingan.
            first.queue_no = -1
            first.updated_at = now
            await session.flush()
            second.queue_no = first_number
            second.queue_code = f"{prefix}-{first_number:03d}"
            second.updated_at = now
            await session.flush()
            first.queue_no = second_number
            first.queue_code = f"{prefix}-{second_number:03d}"
            await session.flush()

            await self._repository.add_history(
                session,
                entry=first,
                action="swap",
                old_value=str(first_number),
                new_value=str(second_number),
                actor_account_id=business_account_id,
                now=now,
            )
            event_suffix = int(now.timestamp())
            for entry in (first, second):
                await self._notify(
                    session,
                    entry,
                    event=f"changed:{entry.queue_no}:{event_suffix}",
                    title="Navbat raqami o‘zgardi",
                    body=f"Yangi navbat raqamingiz: {entry.queue_code}.",
                    action_type="medical_queue_changed",
                )
            await session.commit()
            return await self._project(session, first.id)

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
        provider = await self._provider_context(
            session, business, item, provider_id
        )
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
            if enforce_schedule and queue_date == local_now.date() and (
                _slot_minutes(slot_value) <= local_now.hour * 60 + local_now.minute
            ):
                raise ApiError(
                    400,
                    "queue_slot_in_past",
                    "Bu vaqt allaqachon o'tib ketgan.",
                )
            if customer_account_id is not None and await self._repository.active_customer_duplicate(
                session,
                business_account_id=business.account_id,
                catalog_item_id=item.id,
                provider_id=provider.id,
                queue_date=queue_date,
                customer_account_id=customer_account_id,
                slot_time=slot_value,
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
            if customer_account_id is not None and await self._repository.active_customer_duplicate(
                session,
                business_account_id=business.account_id,
                catalog_item_id=item.id,
                provider_id=provider.id,
                queue_date=queue_date,
                customer_account_id=customer_account_id,
                slot_time=None,
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

    async def _public_context(
        self,
        session: AsyncSession,
        business_public_id: str,
        item_public_id: str,
    ) -> tuple[BusinessProfile, CatalogItem]:
        business = await self._repository.business_by_public_id(
            session, business_public_id
        )
        if business is None:
            raise ApiError(404, "queue_business_not_found", "Biznes profil topilmadi.")
        self._require_direction(business)
        item = await self._enabled_item(session, business.account_id, item_public_id)
        return business, item

    async def _business(
        self,
        session: AsyncSession,
        account_id: int,
    ) -> BusinessProfile:
        business = await self._repository.business(session, account_id)
        if business is None:
            raise ApiError(404, "queue_business_not_found", "Biznes profil topilmadi.")
        self._require_direction(business)
        return business

    def _require_direction(self, business: BusinessProfile) -> None:
        if str(business.direction or "").strip() not in QUEUE_DIRECTIONS:
            raise ApiError(
                403,
                "queue_direction_forbidden",
                "Bu yo'nalishda navbat tizimi ishlamaydi.",
            )

    async def _enabled_item(
        self,
        session: AsyncSession,
        business_account_id: int,
        public_id: str,
    ) -> CatalogItem:
        item = await self._repository.enabled_item(
            session,
            business_account_id=business_account_id,
            public_id=public_id,
        )
        if item is None:
            raise ApiError(
                400,
                "queue_service_disabled",
                "Bu xizmat uchun navbat yoqilmagan.",
            )
        return item

    async def _provider_context(
        self,
        session: AsyncSession,
        business: BusinessProfile,
        item: CatalogItem,
        provider_id: int,
    ) -> QueueProvider:
        provider = await self._repository.provider(
            session,
            provider_id=provider_id,
            business_account_id=business.account_id,
        )
        linked = provider is not None and await self._repository.provider_linked_to_item(
            session,
            provider_id=provider.id,
            catalog_item_id=item.id,
        )
        if provider is None or provider.status != "active" or not linked:
            raise ApiError(
                400,
                "queue_provider_not_assigned",
                "Xizmat ko'rsatuvchi hali biriktirilmagan.",
            )
        if await self._staff_source_exists(session, business):
            active_staff_ids = {
                int(row["id"])
                for row in await self._staff_rows(session, business)
            }
            if provider.legacy_staff_id not in active_staff_ids:
                raise ApiError(
                    400,
                    "queue_provider_not_assigned",
                    "Xizmat ko'rsatuvchi hali biriktirilmagan.",
                )
        return provider

    async def _provider_items(
        self,
        session: AsyncSession,
        business_account_id: int,
        body: QueueProviderWrite,
    ) -> list[CatalogItem]:
        items = await self._repository.enabled_items_by_public_ids(
            session,
            business_account_id=business_account_id,
            public_ids=body.item_public_ids,
        )
        by_public = {self._item_public_id(item): item for item in items}
        if len(by_public) != len(body.item_public_ids) or any(
            public_id not in by_public for public_id in body.item_public_ids
        ):
            raise ApiError(
                400,
                "queue_enabled_service_required",
                "Navbat yoqilgan xizmatni tanlang.",
            )
        return [by_public[public_id] for public_id in body.item_public_ids]

    def _provider_times(self, body: QueueProviderWrite) -> tuple[time, time]:
        work_start = _clock(body.work_start)
        work_end = _clock(body.work_end)
        if work_start >= work_end:
            raise ApiError(
                400,
                "queue_provider_hours_invalid",
                "Ish vaqti noto'g'ri.",
            )
        return work_start, work_end

    async def _staff_rows(
        self,
        session: AsyncSession,
        business: BusinessProfile,
    ) -> list[dict[str, object]]:
        source: list = []
        for resource in ("staff", "business_staff", "employees"):
            source = await self._cabinet_repository.read_resource(
                session,
                account_id=business.account_id,
                account_type="business",
                resource=resource,
            )
            if source:
                break
            fallback = (business.cabinet_payload or {}).get(resource)
            if isinstance(fallback, list) and fallback:
                source = fallback
                break
        rows: list[dict[str, object]] = []
        seen: set[int] = set()
        for source_row in source:
            if not isinstance(source_row, dict):
                continue
            try:
                identifier = int(source_row.get("id") or 0)
            except (TypeError, ValueError):
                continue
            if not identifier or identifier in seen:
                continue
            if str(source_row.get("status") or "active") != "active":
                continue
            seen.add(identifier)
            rows.append({
                "id": identifier,
                "name": str(source_row.get("name") or "")[:120],
                "profession": str(source_row.get("profession") or "Xodim")[:120],
            })
        rows.sort(key=lambda row: str(row["name"]).casefold())
        return rows

    async def _active_staff(
        self,
        session: AsyncSession,
        business: BusinessProfile,
        staff_id: int,
    ) -> dict[str, object]:
        staff = next(
            (
                row
                for row in await self._staff_rows(session, business)
                if int(row["id"]) == staff_id
            ),
            None,
        )
        if staff is None:
            raise ApiError(400, "queue_active_staff_required", "Faol xodimni tanlang.")
        return staff

    async def _staff_source_exists(
        self,
        session: AsyncSession,
        business: BusinessProfile,
    ) -> bool:
        for resource in ("staff", "business_staff", "employees"):
            if await self._cabinet_repository.has_resource(
                session,
                account_id=business.account_id,
                account_type="business",
                resource=resource,
            ):
                return True
            if isinstance((business.cabinet_payload or {}).get(resource), list):
                return True
        return False

    def _provider_read(
        self,
        provider: QueueProvider,
        items: list[CatalogItem],
        *,
        queue_count: int = 0,
    ) -> QueueProviderRead:
        return QueueProviderRead(
            id=provider.id,
            staff_id=provider.legacy_staff_id,
            name=provider.staff_name_snapshot,
            profession=provider.profession_snapshot,
            specialty=provider.specialty,
            experience_years=provider.experience_years,
            qualification=provider.qualification,
            work_days=provider.work_days,
            work_start=_clock_text(provider.work_start),
            work_end=_clock_text(provider.work_end),
            avg_minutes=provider.avg_minutes,
            room=provider.room,
            bio=provider.bio,
            status=provider.status,
            mode=provider.mode,
            item_public_ids=[self._item_public_id(item) for item in items],
            queue_count=queue_count,
        )

    async def _project(
        self,
        session: AsyncSession,
        queue_id: int,
    ) -> QueueEntryRead:
        row = await self._repository.projected_entry(session, queue_id)
        if row is None:
            raise ApiError(404, "queue_not_found", "Navbat topilmadi.")
        return self._entry_read(*row)

    def _entry_read(
        self,
        entry: QueueEntry,
        avg_minutes: int,
        ahead_count: int,
        business_name: str,
        business_direction: str,
    ) -> QueueEntryRead:
        active = entry.status in ACTIVE_STATUSES
        ahead = int(ahead_count or 0) if active else 0
        average = int(avg_minutes or 0)
        return QueueEntryRead(
            id=entry.id,
            business_account_id=entry.business_account_id,
            business_name=str(business_name or ""),
            business_direction=str(business_direction or ""),
            customer_account_id=entry.customer_account_id,
            item_public_id=(
                build_content_public_id("service", entry.catalog_item_id)
                if entry.catalog_item_id is not None
                else ""
            ),
            provider_id=entry.provider_id,
            patient_name=entry.patient_name,
            phone=entry.phone,
            service_name=entry.service_name_snapshot,
            provider_name=entry.provider_name_snapshot,
            queue_date=entry.queue_date,
            queue_no=entry.queue_no,
            queue_code=entry.queue_code,
            source=entry.source,
            status=entry.status,
            note=entry.note,
            slot_time=_clock_text(entry.slot_time),
            ahead_count=ahead,
            avg_minutes=average,
            wait_minutes=ahead * average if active and average > 0 else 0,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )

    async def _notify(
        self,
        session: AsyncSession,
        entry: QueueEntry,
        *,
        event: str,
        title: str,
        body: str,
        action_type: str,
    ) -> None:
        if entry.customer_account_id is None:
            return
        await self._notifications.append(
            session,
            account_id=entry.customer_account_id,
            account_type="user",
            row={
                "event_key": f"medical_queue:{entry.id}:{event}",
                "title": title,
                "body": body,
                "action_type": action_type,
                "requires_action": 0,
                "is_read": 0,
                "created_at": int(self._now().timestamp()),
                "medical_queue_id": entry.id,
            },
        )

    def _works_on(self, provider: QueueProvider, queue_date: date) -> bool:
        days = {
            part.strip()
            for part in str(provider.work_days or "").split(",")
            if part.strip()
        }
        return not days or str(queue_date.isoweekday()) in days

    def _validate_date(self, queue_date: date) -> None:
        if queue_date < self._local_now().date():
            raise ApiError(
                400,
                "queue_date_in_past",
                "O'tgan sanaga navbat olib bo'lmaydi.",
            )

    def _now(self) -> datetime:
        value = self._now_provider()
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    def _local_now(self) -> datetime:
        return self._now().astimezone(UZBEKISTAN_TZ)

    @staticmethod
    def _item_public_id(item: CatalogItem) -> str:
        return item.public_id or build_content_public_id(item.kind, item.id)
