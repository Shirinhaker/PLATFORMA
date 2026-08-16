"""Muammoli buyurtma: ochish va yechim tanlash."""

from __future__ import annotations

from datetime import UTC, datetime

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.orders.schemas import (
    OrderProblemCreate,
    OrderProblemSolution,
    OrderRead,
)
from app.orders.service_parts.base import OrderServiceBase


class ProblemsMixin(OrderServiceBase):
    async def open_problem(
        self,
        *,
        order_id: int,
        account_id: int,
        account_type: AccountType,
        body: OrderProblemCreate,
    ) -> OrderRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            if side != "provider":
                raise ApiError(
                    403,
                    "order_provider_required",
                    "Bu amal faqat xizmat ko'rsatuvchiga tegishli.",
                )
            if order.status in {"done", "cancelled", "rejected"}:
                raise ApiError(
                    409,
                    "order_problem_finished",
                    "Yakunlangan buyurtmada muammo ochib bo'lmaydi.",
                )
            if order.payment_status not in {"submitted", "recheck", "disputed"}:
                raise ApiError(
                    409,
                    "order_problem_invalid",
                    "Avval buyurtmachi to'lov qilganini bildirishi kerak.",
                )
            now = datetime.now(UTC)
            order.problem_open = True
            order.problem_reason = body.reason
            order.problem_note = body.note.strip()
            order.problem_solution = ""
            order.problem_opened_at = now
            order.problem_resolved_at = None
            order.payment_status = "disputed"
            order.updated_at = now
            self._changed(order, side, "problem", now)
            await self._event(session, "order.problem_opened", order, account_id)
            await session.commit()
            return await self._project(session, order, side)

    async def choose_problem_solution(
        self,
        *,
        order_id: int,
        account_id: int,
        account_type: AccountType,
        body: OrderProblemSolution,
    ) -> OrderRead:
        async with self._session_factory() as session:
            order, side = await self._owned(session, order_id, account_id, lock=True)
            if side != "customer" or not order.problem_open:
                raise ApiError(
                    409,
                    "order_problem_solution_invalid",
                    "Bu buyurtmada ochiq muammo yo'q.",
                )
            now = datetime.now(UTC)
            order.problem_solution = body.solution
            if body.solution == "new_receipt":
                order.payment_status = "recheck"
            elif body.solution == "pickup":
                order.order_type = "pickup"
            order.updated_at = now
            self._changed(order, side, "problem_solution", now)
            await self._event(
                session, "order.problem_solution_selected", order, account_id
            )
            await session.commit()
            return await self._project(session, order, side)
