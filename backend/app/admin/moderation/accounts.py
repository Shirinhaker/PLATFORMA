"""Akkauntlar royxati va kartochkasi."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select

from app.accounts.model import Account, AccountType
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
from app.profiles.model import BusinessProfile, UserProfile


class AccountsMixin(AdminModerationServiceBase):
    async def list_accounts(
        self,
        *,
        actor_type: str,
        query: str = "",
        restriction: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        _require(
            actor_type,
            ACTOR_TYPES,
            "admin_actor_type_invalid",
            "Akkaunt turi noto‘g‘ri.",
        )
        if restriction and restriction not in RESTRICTIONS:
            raise ApiError(400, "admin_restriction_invalid", "Cheklov turi noto‘g‘ri.")
        profile = UserProfile if actor_type == "user" else BusinessProfile
        account_type = (
            AccountType.USER if actor_type == "user" else AccountType.BUSINESS
        )
        statement = (
            select(
                Account.id,
                Account.login,
                Account.telegram_user_id,
                profile.name,
                profile.phone,
            )
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
        statement = statement.order_by(Account.id.desc()).limit(max(1, min(200, limit)))

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
            result.append(
                {
                    "actor_type": actor_type,
                    "account_id": account_id,
                    "login": login,
                    "telegram_user_id": telegram_id,
                    "name": name or "",
                    "phone": phone or "",
                    "restrictions": sorted(marks),
                }
            )
        return result

    async def account_detail(
        self, *, actor_type: str, account_id: int
    ) -> dict[str, Any]:
        _require(
            actor_type,
            ACTOR_TYPES,
            "admin_actor_type_invalid",
            "Akkaunt turi noto‘g‘ri.",
        )
        profile = UserProfile if actor_type == "user" else BusinessProfile
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(Account, profile)
                    .join(profile, profile.account_id == Account.id, isouter=True)
                    .where(Account.id == account_id)
                )
            ).first()
            if row is None:
                raise ApiError(404, "admin_account_not_found", "Akkaunt topilmadi.")
            account, profile_row = row
            restrictions = list(
                (
                    await session.scalars(
                        select(AccountRestriction)
                        .where(
                            AccountRestriction.actor_type == actor_type,
                            AccountRestriction.actor_id == account_id,
                        )
                        .order_by(AccountRestriction.id.desc())
                    )
                ).all()
            )
            notes = list(
                (
                    await session.scalars(
                        select(AdminAccountNote)
                        .where(
                            AdminAccountNote.actor_type == actor_type,
                            AdminAccountNote.actor_id == account_id,
                        )
                        .order_by(AdminAccountNote.id.desc())
                        .limit(50)
                    )
                ).all()
            )
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
