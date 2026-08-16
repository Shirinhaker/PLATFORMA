"""Oshxona: zakazni "tayyor" deb belgilash."""

from __future__ import annotations

from app.core.errors import ApiError
from app.dining.schemas import (
    DiningKitchenUpdate,
    DiningOrderRead,
)
from app.dining.service_parts.base import DiningServiceBase


class KitchenMixin(DiningServiceBase):
    async def set_kitchen_status(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        order_id: int,
        body: DiningKitchenUpdate,
    ) -> DiningOrderRead:
        """Oshpaz taomni tayyorlanmoqda yoki tayyor deb belgilaydi."""
        self._require(permissions, "kitchen")
        now = self._now()
        async with self._session_factory() as session:
            order = await self._require_order(
                session,
                business_account_id=business_account_id,
                order_id=order_id,
                lock=True,
            )
            if order.status != "active":
                raise ApiError(
                    409,
                    "dining_order_closed",
                    "Yakunlangan buyurtma o‘zgartirilmaydi.",
                )
            if order.problem_open:
                raise ApiError(
                    409,
                    "dining_order_problem_open",
                    "Muammoli zakazni avval kassada hal qiling.",
                )
            order.kitchen_status = body.status
            order.updated_at = now
            place_name, place_kind = await self._place_of(session, order)
            if body.status == "done":
                await self._notify(
                    session,
                    business_account_id=business_account_id,
                    event_key=f"dining:{order.id}:ready:waiter",
                    title="Taom tayyor bo‘ldi",
                    body_text=(
                        f"{order.waiter_name or 'Ofitsiant'} uchun zakazni "
                        "olib ketishingiz mumkin."
                    ),
                    action_type="dining_waiter",
                    order_id=order.id,
                    target_perm="dining_internal",
                    now=now,
                )
                await self._resolve(
                    session,
                    business_account_id=business_account_id,
                    order_id=order.id,
                    action_type="dining_kitchen",
                    now=now,
                )
            items = await self._repository.items(session, order_id=order.id)
            result = self._order_read(order, place_name, place_kind, items)
            await session.commit()
        return result
