"""Kontent holati: elon, mahsulot, reklama."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.admin.audit import append_audit
from app.admin.moderation.base import AdminModerationServiceBase
from app.admin.moderation.helpers import (
    _require,
    _unix,
)
from app.admin.moderation_model import (
    CONTENT_KINDS,
    CONTENT_STATUSES,
    ContentModeration,
)
from app.core.errors import ApiError


class ContentMixin(AdminModerationServiceBase):
    async def set_content_status(
        self,
        *,
        content_kind: str,
        content_id: int,
        status: str,
        reason: str,
        admin_tg_id: int,
        meta: dict[str, str] | None,
    ) -> dict[str, Any]:
        _require(
            content_kind,
            CONTENT_KINDS,
            "admin_content_kind_invalid",
            "Kontent turi noto‘g‘ri.",
        )
        _require(
            status,
            CONTENT_STATUSES,
            "admin_content_status_invalid",
            "Kontent holati noto‘g‘ri.",
        )
        reason = reason.strip()
        if status != "visible" and not reason:
            raise ApiError(400, "admin_reason_required", "Sabab kiritilishi shart.")
        now = self._now()
        async with self._session_factory() as session:
            previous = await self._content_status(
                session, content_kind=content_kind, content_id=content_id
            )
            row = ContentModeration(
                content_kind=content_kind,
                content_id=content_id,
                status=status,
                reason=reason,
                changed_by_tg_id=admin_tg_id,
                created_at=now,
            )
            session.add(row)
            await session.flush()
            await append_audit(
                session,
                admin_tg_id=admin_tg_id,
                action=f"content.{status}",
                target_kind=content_kind,
                target_id=content_id,
                before={"status": previous},
                after={"status": status},
                reason=reason,
                meta=meta,
                now=now,
            )
            result = {
                "content_kind": content_kind,
                "content_id": content_id,
                "status": status,
                "previous_status": previous,
                "created_at": _unix(now),
            }
            await session.commit()
        return result

    async def content_status(
        self, *, content_kind: str, content_id: int
    ) -> dict[str, Any]:
        _require(
            content_kind,
            CONTENT_KINDS,
            "admin_content_kind_invalid",
            "Kontent turi noto‘g‘ri.",
        )
        async with self._session_factory() as session:
            row = await session.scalar(
                select(ContentModeration)
                .where(
                    ContentModeration.content_kind == content_kind,
                    ContentModeration.content_id == content_id,
                )
                .order_by(ContentModeration.id.desc())
                .limit(1)
            )
            history = list(
                (
                    await session.scalars(
                        select(ContentModeration)
                        .where(
                            ContentModeration.content_kind == content_kind,
                            ContentModeration.content_id == content_id,
                        )
                        .order_by(ContentModeration.id.desc())
                        .limit(20)
                    )
                ).all()
            )
            detail = {
                "content_kind": content_kind,
                "content_id": content_id,
                "status": row.status if row is not None else "visible",
                "history": [
                    {
                        "status": item.status,
                        "reason": item.reason,
                        "changed_by_tg_id": item.changed_by_tg_id,
                        "created_at": _unix(item.created_at),
                    }
                    for item in history
                ],
            }
            await session.rollback()
        return detail
