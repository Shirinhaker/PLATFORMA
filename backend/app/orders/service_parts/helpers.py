"""Buyurtma xizmati uchun umumiy tiplar va konstantalar."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.orders.model import Order

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


ImageUrlProvider = Callable[[str], str]


FRACTIONAL_UNITS = frozenset({"kg", "g", "litr", "ml", "metr", "sm", "m²", "soat"})


class TaxiOrderLink(Protocol):
    async def after_order_ready(self, session: AsyncSession, order: Order) -> None: ...

    async def after_order_handoff(
        self, session: AsyncSession, order_id: int
    ) -> None: ...

    async def after_order_received(
        self, session: AsyncSession, order_id: int
    ) -> None: ...
