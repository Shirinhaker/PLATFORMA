"""Umumiy asos: egalik, urinishlar tarixi, hodisa yozuvi."""

from __future__ import annotations

import time
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.payments.model import (
    PaymentAttempt,
    PaymentEvent,
    PaymentRequest,
)
from app.payments.schemas import (
    PaymentReceipt,
)
from app.payments.service_parts.helpers import (
    Activator,
    SessionFactory,
)


class PaymentServiceBase:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        now: Callable[[], int] | None = None,
        activator: Activator | None = None,
        download_url_provider: Callable[..., str] | None = None,
        advertisement_service: object | None = None,
        listing_service: object | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._now = now or (lambda: int(time.time()))
        self._activator = activator
        self._download_url = download_url_provider
        self._advertisements = advertisement_service
        self._listings = listing_service

    async def _owned(
        self,
        session: AsyncSession,
        account_id: int,
        payment_id: int,
        *,
        lock: bool = False,
    ) -> PaymentRequest:
        statement = select(PaymentRequest).where(
            PaymentRequest.id == payment_id,
            PaymentRequest.account_id == account_id,
        )
        if lock:
            statement = statement.with_for_update()
        request = await session.scalar(statement)
        if request is None:
            raise ApiError(404, "payment_not_found", "To'lov topilmadi.")
        return request

    @staticmethod
    async def _attempts(
        session: AsyncSession,
        payment_id: int,
    ) -> list[PaymentAttempt]:
        return list(
            (
                await session.scalars(
                    select(PaymentAttempt)
                    .where(PaymentAttempt.payment_request_id == payment_id)
                    .order_by(PaymentAttempt.attempt_no)
                )
            ).all()
        )

    @staticmethod
    def _add_attempt(
        session: AsyncSession,
        request: PaymentRequest,
        receipt: PaymentReceipt,
        *,
        attempt_no: int,
        now: int,
    ) -> None:
        session.add(
            PaymentAttempt(
                payment_request_id=request.id,
                attempt_no=attempt_no,
                receipt_object_key=receipt.object_key,
                receipt_filename=receipt.filename,
                receipt_mime=receipt.mime,
                receipt_sha256=receipt.sha256,
                submitted_at=now,
                review_status="pending",
            )
        )

    @staticmethod
    def _add_event(
        session: AsyncSession,
        request: PaymentRequest,
        *,
        from_status: str,
        to_status: str,
        actor_kind: str,
        actor_id: str,
        now: int,
        reason: str = "",
    ) -> None:
        session.add(
            PaymentEvent(
                payment_request_id=request.id,
                from_status=from_status,
                to_status=to_status,
                actor_kind=actor_kind,
                actor_id=actor_id,
                reason=reason,
                event_metadata={},
                created_at=now,
            )
        )
