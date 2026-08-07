"""Akkaunt cheklovlari, ichki izohlar va kontent ko'rinishi.

v1656 `moderation.py` bilan bir xil qoidalar:

- `content_hidden` egasining kabinetidagi ma'lumotni **o'chirmaydi**,
  faqat public qidiruv, xarita va takliflardan yashiradi;
- `account_blocked` yozish amallarini to'xtatadi;
- ikkalasi mustaqil — biri ikkinchisini yoqmaydi.

Har bir o'zgarish audit jurnaliga yoziladi.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.admin.audit import append_audit
from app.admin.moderation_model import (
    ACTOR_TYPES,
    CONTENT_KINDS,
    CONTENT_STATUSES,
    RESTRICTIONS,
    AccountRestriction,
    AdminAccountNote,
    ContentModeration,
)
from app.core.errors import ApiError
from app.profiles.model import BusinessProfile, UserProfile


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def _require(value: str, allowed: tuple[str, ...], code: str, label: str) -> str:
    if value not in allowed:
        raise ApiError(400, code, label)
    return value


def _unix(value: datetime | None) -> int:
    return int(value.timestamp()) if value is not None else 0


class AdminModerationService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._now = now_provider

    # ------------------------------------------------------------ qidiruv

    async def list_accounts(
        self,
        *,
        actor_type: str,
        query: str = "",
        restriction: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        _require(
            actor_type, ACTOR_TYPES, "admin_actor_type_invalid",
            "Akkaunt turi noto‘g‘ri.",
        )
        if restriction and restriction not in RESTRICTIONS:
            raise ApiError(
                400, "admin_restriction_invalid", "Cheklov turi noto‘g‘ri."
            )
        profile = UserProfile if actor_type == "user" else BusinessProfile
        account_type = (
            AccountType.USER if actor_type == "user" else AccountType.BUSINESS
        )
        statement = (
            select(Account.id, Account.login, Account.telegram_user_id,
                   profile.name, profile.phone)
            .join(profile, profile.account_id == Account.id, isouter=True)
            .where(Account.account_type == account_type)
        )
        needle = query.strip()
        if needle:
            like = f"%{needle.lower()}%"
            conditions = [
                func.lower(Account.login).like(like),
                func.lower(profile.name).like(like),
                profile.phone.like(f"%{needle}%"),
            ]
            if needle.isdigit():
                conditions.append(Account.telegram_user_id == int(needle))
            statement = statement.where(or_(*conditions))
        statement = statement.order_by(Account.id.desc()).limit(
            max(1, min(200, limit))
        )

        async with self._session_factory() as session:
            rows = (await session.execute(statement)).all()
            active = await self._active_restrictions(
                session,
                actor_type=actor_type,
                actor_ids=[row[0] for row in rows],
            )
            await session.rollback()

        result = []
        for account_id, login, telegram_id, name, phone in rows:
            marks = active.get(account_id, ())
            if restriction and restriction not in marks:
                continue
            result.append({
                "actor_type": actor_type,
                "account_id": account_id,
                "login": login,
                "telegram_user_id": telegram_id,
                "name": name or "",
                "phone": phone or "",
                "restrictions": sorted(marks),
            })
        return result

    async def account_detail(
        self, *, actor_type: str, account_id: int
    ) -> dict[str, Any]:
        _require(
            actor_type, ACTOR_TYPES, "admin_actor_type_invalid",
            "Akkaunt turi noto‘g‘ri.",
        )
        profile = UserProfile if actor_type == "user" else BusinessProfile
        async with self._session_factory() as session:
            row = (await session.execute(
                select(Account, profile)
                .join(profile, profile.account_id == Account.id, isouter=True)
                .where(Account.id == account_id)
            )).first()
            if row is None:
                raise ApiError(
                    404, "admin_account_not_found", "Akkaunt topilmadi."
                )
            account, profile_row = row
            restrictions = list((await session.scalars(
                select(AccountRestriction)
                .where(
                    AccountRestriction.actor_type == actor_type,
                    AccountRestriction.actor_id == account_id,
                )
                .order_by(AccountRestriction.id.desc())
            )).all())
            notes = list((await session.scalars(
                select(AdminAccountNote)
                .where(
                    AdminAccountNote.actor_type == actor_type,
                    AdminAccountNote.actor_id == account_id,
                )
                .order_by(AdminAccountNote.id.desc())
                .limit(50)
            )).all())
            detail = {
                "actor_type": actor_type,
                "account_id": account.id,
                "login": account.login,
                "telegram_user_id": account.telegram_user_id,
                "status": account.status,
                "created_at": _unix(account.created_at),
                "name": getattr(profile_row, "name", "") or "",
                "phone": getattr(profile_row, "phone", "") or "",
                "restrictions": [
                    {
                        "id": item.id,
                        "restriction": item.restriction,
                        "status": item.status,
                        "reason": item.reason,
                        "created_by_tg_id": item.created_by_tg_id,
                        "created_at": _unix(item.created_at),
                        "revoked_reason": item.revoked_reason,
                        "revoked_at": _unix(item.revoked_at),
                    }
                    for item in restrictions
                ],
                "notes": [
                    {
                        "id": note.id,
                        "note": note.note,
                        "admin_tg_id": note.admin_tg_id,
                        "created_at": _unix(note.created_at),
                    }
                    for note in notes
                ],
            }
            await session.rollback()
        return detail

    # ---------------------------------------------------------- cheklovlar

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
            actor_type, ACTOR_TYPES, "admin_actor_type_invalid",
            "Akkaunt turi noto‘g‘ri.",
        )
        _require(
            restriction, RESTRICTIONS, "admin_restriction_invalid",
            "Cheklov turi noto‘g‘ri.",
        )
        reason = reason.strip()
        if not reason:
            raise ApiError(
                400, "admin_reason_required", "Sabab kiritilishi shart."
            )
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
            actor_type, ACTOR_TYPES, "admin_actor_type_invalid",
            "Akkaunt turi noto‘g‘ri.",
        )
        _require(
            restriction, RESTRICTIONS, "admin_restriction_invalid",
            "Cheklov turi noto‘g‘ri.",
        )
        reason = reason.strip()
        if not reason:
            raise ApiError(
                400, "admin_reason_required", "Sabab kiritilishi shart."
            )
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
            actor_type, ACTOR_TYPES, "admin_actor_type_invalid",
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

    # ------------------------------------------------------------- kontent

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
            content_kind, CONTENT_KINDS, "admin_content_kind_invalid",
            "Kontent turi noto‘g‘ri.",
        )
        _require(
            status, CONTENT_STATUSES, "admin_content_status_invalid",
            "Kontent holati noto‘g‘ri.",
        )
        reason = reason.strip()
        if status != "visible" and not reason:
            raise ApiError(
                400, "admin_reason_required", "Sabab kiritilishi shart."
            )
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
            content_kind, CONTENT_KINDS, "admin_content_kind_invalid",
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
            history = list((await session.scalars(
                select(ContentModeration)
                .where(
                    ContentModeration.content_kind == content_kind,
                    ContentModeration.content_id == content_id,
                )
                .order_by(ContentModeration.id.desc())
                .limit(20)
            )).all())
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

    # ------------------------------------------------------------ yordamchi

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
            raise ApiError(
                404, "admin_account_not_found", "Akkaunt topilmadi."
            )

    @staticmethod
    async def _active_restrictions(
        session: AsyncSession, *, actor_type: str, actor_ids: list[int]
    ) -> dict[int, set[str]]:
        if not actor_ids:
            return {}
        rows = (await session.execute(
            select(AccountRestriction.actor_id, AccountRestriction.restriction)
            .where(
                AccountRestriction.actor_type == actor_type,
                AccountRestriction.actor_id.in_(actor_ids),
                AccountRestriction.status == "active",
            )
        )).all()
        grouped: dict[int, set[str]] = {}
        for actor_id, restriction in rows:
            grouped.setdefault(actor_id, set()).add(restriction)
        return grouped
