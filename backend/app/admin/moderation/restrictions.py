"""Cheklov qoyish, olib tashlash va izoh."""

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
    ACTOR_TYPES,
    RESTRICTIONS,
    AccountRestriction,
    AdminAccountNote,
)
from app.core.errors import ApiError


class RestrictionsMixin(AdminModerationServiceBase):
    async def restrict(
        self,
        *,
        actor_type: str,
        account_id: int,
        restriction: str,
        reason: str,
        admin_tg_id: int,
        meta: dict[str, str] | None,
    ) -> dict[str, Any]:
        _require(
            actor_type,
            ACTOR_TYPES,
            "admin_actor_type_invalid",
            "Akkaunt turi noto‘g‘ri.",
        )
        _require(
            restriction,
            RESTRICTIONS,
            "admin_restriction_invalid",
            "Cheklov turi noto‘g‘ri.",
        )
        reason = reason.strip()
        if not reason:
            raise ApiError(400, "admin_reason_required", "Sabab kiritilishi shart.")
        now = self._now()
        async with self._session_factory() as session:
            await self._require_account(session, actor_type, account_id)
            existing = await session.scalar(
                select(AccountRestriction)
                .where(
                    AccountRestriction.actor_type == actor_type,
                    AccountRestriction.actor_id == account_id,
                    AccountRestriction.restriction == restriction,
                    AccountRestriction.status == "active",
                )
                .with_for_update()
            )
            if existing is not None:
                # Idempotent: takroriy cheklov ikkinchi yozuv yaratmaydi.
                result = {"id": existing.id, "already_active": True}
                await session.rollback()
                return result
            row = AccountRestriction(
                actor_type=actor_type,
                actor_id=account_id,
                restriction=restriction,
                status="active",
                reason=reason,
                created_by_tg_id=admin_tg_id,
                created_at=now,
            )
            session.add(row)
            await session.flush()
            await append_audit(
                session,
                admin_tg_id=admin_tg_id,
                action="account.restrict",
                target_kind=actor_type,
                target_id=account_id,
                before={"restriction": restriction, "status": "none"},
                after={"restriction": restriction, "status": "active"},
                reason=reason,
                meta=meta,
                now=now,
            )
            result = {"id": row.id, "already_active": False}
            await session.commit()
        return result

    async def unrestrict(
        self,
        *,
        actor_type: str,
        account_id: int,
        restriction: str,
        reason: str,
        admin_tg_id: int,
        meta: dict[str, str] | None,
    ) -> dict[str, Any]:
        _require(
            actor_type,
            ACTOR_TYPES,
            "admin_actor_type_invalid",
            "Akkaunt turi noto‘g‘ri.",
        )
        _require(
            restriction,
            RESTRICTIONS,
            "admin_restriction_invalid",
            "Cheklov turi noto‘g‘ri.",
        )
        reason = reason.strip()
        if not reason:
            raise ApiError(400, "admin_reason_required", "Sabab kiritilishi shart.")
        now = self._now()
        async with self._session_factory() as session:
            row = await session.scalar(
                select(AccountRestriction)
                .where(
                    AccountRestriction.actor_type == actor_type,
                    AccountRestriction.actor_id == account_id,
                    AccountRestriction.restriction == restriction,
                    AccountRestriction.status == "active",
                )
                .with_for_update()
            )
            if row is None:
                raise ApiError(
                    404,
                    "admin_restriction_not_found",
                    "Faol cheklov topilmadi.",
                )
            row.status = "revoked"
            row.revoked_by_tg_id = admin_tg_id
            row.revoked_reason = reason
            row.revoked_at = now
            await append_audit(
                session,
                admin_tg_id=admin_tg_id,
                action="account.unrestrict",
                target_kind=actor_type,
                target_id=account_id,
                before={"restriction": restriction, "status": "active"},
                after={"restriction": restriction, "status": "revoked"},
                reason=reason,
                meta=meta,
                now=now,
            )
            result = {"id": row.id, "already_active": False}
            await session.commit()
        return result

    async def add_note(
        self,
        *,
        actor_type: str,
        account_id: int,
        note: str,
        admin_tg_id: int,
        meta: dict[str, str] | None,
    ) -> dict[str, Any]:
        _require(
            actor_type,
            ACTOR_TYPES,
            "admin_actor_type_invalid",
            "Akkaunt turi noto‘g‘ri.",
        )
        note = note.strip()
        if not note:
            raise ApiError(400, "admin_note_required", "Izoh bo‘sh bo‘lmasin.")
        now = self._now()
        async with self._session_factory() as session:
            await self._require_account(session, actor_type, account_id)
            row = AdminAccountNote(
                actor_type=actor_type,
                actor_id=account_id,
                note=note[:2000],
                admin_tg_id=admin_tg_id,
                created_at=now,
            )
            session.add(row)
            await session.flush()
            await append_audit(
                session,
                admin_tg_id=admin_tg_id,
                action="account.note",
                target_kind=actor_type,
                target_id=account_id,
                before={},
                after={"note_id": row.id},
                reason="",
                meta=meta,
                now=now,
            )
            result = {
                "id": row.id,
                "note": row.note,
                "admin_tg_id": admin_tg_id,
                "created_at": _unix(now),
            }
            await session.commit()
        return result
