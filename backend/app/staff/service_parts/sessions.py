"""Xodim seansi: kirish, tekshirish, chiqish."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from app.auth.schemas import SessionIdentity
from app.auth.security import (
    sha256_token,
    verify_password_with_rehash,
)
from app.staff.model import StaffSession
from app.staff.service_parts.base import StaffServiceBase


class SessionsMixin(StaffServiceBase):
    async def login(
        self,
        firm_login: str,
        staff_login: str,
        password: str,
    ) -> tuple[str, SessionIdentity]:
        firm = firm_login.strip().casefold()
        login = staff_login.strip().casefold()
        async with self._session_factory() as session:
            account = await self._repository.business_account_by_login(session, firm)
            if account is None:
                raise self._invalid_credentials()
            member = await self._repository.member_by_login(
                session,
                business_account_id=account.id,
                login=login,
            )
            if (
                member is None
                or not member.can_login
                or member.status != "active"
                or not member.password_hash
            ):
                raise self._invalid_credentials()
            checked = verify_password_with_rehash(member.password_hash, password)
            if not checked.valid:
                raise self._invalid_credentials()
            if checked.replacement_hash:
                member.password_hash = checked.replacement_hash
            raw_token = secrets.token_urlsafe(32)
            now = self._now()
            expires_at = now + timedelta(seconds=self._settings.session_ttl_seconds)
            session.add(
                StaffSession(
                    staff_id=member.id,
                    token_hash=sha256_token(raw_token),
                    created_at=now,
                    expires_at=expires_at,
                    last_used_at=now,
                    revoked_at=None,
                )
            )
            await session.commit()
            return raw_token, self._identity(raw_token, member, expires_at)

    async def resolve_session(
        self,
        raw_token: str,
        now: datetime,
    ) -> SessionIdentity | None:
        async with self._session_factory() as session:
            stored = await self._repository.session_by_token_hash(
                session,
                token_hash=sha256_token(raw_token),
                now=now,
                lock=True,
            )
            if stored is None:
                await session.rollback()
                return None
            member = await self._repository.member(
                session, staff_id=stored.staff_id, lock=False
            )
            if (
                member is None
                or member.status != "active"
                or not member.can_login
                or not member.password_hash
            ):
                stored.revoked_at = now
                await session.commit()
                return None
            stored.last_used_at = now
            await session.commit()
            return self._identity(raw_token, member, stored.expires_at)

    async def revoke_session(self, raw_token: str, now: datetime) -> None:
        async with self._session_factory() as session:
            stored = await self._repository.session_by_token_hash(
                session,
                token_hash=sha256_token(raw_token),
                now=now,
                lock=True,
            )
            if stored is not None:
                stored.revoked_at = now
                await session.commit()
            else:
                await session.rollback()
