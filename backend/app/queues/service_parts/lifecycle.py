"""Navbat holati: bekor qilish, o'zgartirish, almashtirish."""

from __future__ import annotations

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.queues.repository import ACTIVE_STATUSES
from app.queues.schemas import (
    QueueEntryRead,
    QueueNotificationRead,
    QueueStatusChange,
    QueueSwap,
)
from app.queues.service_parts.base import QueueServiceBase
from app.queues.service_parts.helpers import (
    TERMINAL_STATUSES,
    _medical_code,
)


class LifecycleMixin(QueueServiceBase):
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
            same_queue = (
                first is not None
                and second is not None
                and first.id != second.id
                and (
                    first.queue_date,
                    first.provider_id,
                    first.catalog_item_id,
                )
                == (
                    second.queue_date,
                    second.provider_id,
                    second.catalog_item_id,
                )
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
