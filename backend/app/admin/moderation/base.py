"""Umumiy asos: akkauntni topish va faol cheklovlar."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.admin.moderation.helpers import (
    SessionFactory,
)
from app.admin.moderation_model import (
    AccountRestriction,
    ContentModeration,
)
from app.core.errors import ApiError


class AdminModerationServiceBase:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._now = now_provider

    @staticmethod
    async def _content_status(
        session: AsyncSession, *, content_kind: str, content_id: int
    ) -> str:
        row = await session.scalar(
            select(ContentModeration.status)
            .where(
                ContentModeration.content_kind == content_kind,
                ContentModeration.content_id == content_id,
            )
            .order_by(ContentModeration.id.desc())
            .limit(1)
        )
        return row or "visible"

    @staticmethod
    async def _require_account(
        session: AsyncSession, actor_type: str, account_id: int
    ) -> None:
        account_type = (
            AccountType.USER if actor_type == "user" else AccountType.BUSINESS
        )
        found = await session.scalar(
            select(Account.id).where(
                Account.id == account_id,
                Account.account_type == account_type,
            )
        )
        if found is None:
            raise ApiError(404, "admin_account_not_found", "Akkaunt topilmadi.")

    @staticmethod
    async def _active_restrictions(
        session: AsyncSession, *, actor_type: str, actor_ids: list[int]
    ) -> dict[int, set[str]]:
        if not actor_ids:
            return {}
        rows = (
            await session.execute(
                select(
                    AccountRestriction.actor_id, AccountRestriction.restriction
                ).where(
                    AccountRestriction.actor_type == actor_type,
                    AccountRestriction.actor_id.in_(actor_ids),
                    AccountRestriction.status == "active",
                )
            )
        ).all()
        grouped: dict[int, set[str]] = {}
        for actor_id, restriction in rows:
            grouped.setdefault(actor_id, set()).add(restriction)
        return grouped
