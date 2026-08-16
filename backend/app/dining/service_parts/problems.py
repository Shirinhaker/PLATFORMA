"""Muammoli zakaz: ochish va hal qilish."""

from __future__ import annotations

from app.core.errors import ApiError
from app.dining.schemas import (
    DiningOrderRead,
    DiningProblemOpen,
)
from app.dining.service_parts.base import DiningServiceBase


class ProblemsMixin(DiningServiceBase):
    async def open_problem(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        order_id: int,
        body: DiningProblemOpen,
    ) -> DiningOrderRead:
        self._require(permissions, "kassa", "payment_problems")
        now = self._now()
        async with self._session_factory() as session:
            order = await self._require_order(
                session,
                business_account_id=business_account_id,
                order_id=order_id,
                lock=True,
            )
            if order.status != "active" or order.payment_status == "confirmed":
                raise ApiError(
                    409,
                    "dining_order_closed",
                    "Yopilgan yoki to‘lovi tasdiqlangan hisob muammoliga "
                    "o‘tkazilmaydi.",
                )
            reason = (body.reason or "Boshqa").strip()[:80]
            order.problem_open = True
            order.problem_reason = reason
            order.problem_note = body.note.strip()
            order.problem_opened_at = now
            order.updated_at = now
            place_name, place_kind = await self._place_of(session, order)
            suffix = f" · {order.problem_note}" if order.problem_note else ""
            await self._notify(
                session,
                business_account_id=business_account_id,
                event_key=f"dining:{order.id}:problem",
                title="Ichki hisobda muammo",
                body_text=f"{reason}{suffix}",
                action_type="dining_problem",
                order_id=order.id,
                target_perm="kassa",
                now=now,
            )
            items = await self._repository.items(session, order_id=order.id)
            result = self._order_read(order, place_name, place_kind, items)
            await session.commit()
        return result

    async def resolve_problem(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        order_id: int,
    ) -> DiningOrderRead:
        self._require(permissions, "kassa", "payment_problems")
        now = self._now()
        async with self._session_factory() as session:
            order = await self._require_order(
                session,
                business_account_id=business_account_id,
                order_id=order_id,
                lock=True,
            )
            place_name, place_kind = await self._place_of(session, order)
            if not order.problem_open:
                items = await self._repository.items(session, order_id=order.id)
                return self._order_read(order, place_name, place_kind, items)
            order.problem_open = False
            order.updated_at = now
            await self._resolve(
                session,
                business_account_id=business_account_id,
                order_id=order.id,
                action_type="dining_problem",
                now=now,
            )
            items = await self._repository.items(session, order_id=order.id)
            result = self._order_read(order, place_name, place_kind, items)
            await session.commit()
        return result
