"""Huquqlar, ish jadvali va kasblar."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.auth.security import (
    hash_password,
)
from app.core.errors import ApiError
from app.staff.model import StaffProfession
from app.staff.permissions import (
    clean_permissions,
)
from app.staff.schemas import (
    StaffAccessWrite,
    StaffMemberRead,
    StaffScheduleWrite,
)
from app.staff.service_parts.base import StaffServiceBase
from app.staff.service_parts.helpers import (
    DEFAULT_PROFESSIONS,
    LOGIN_RE,
)


class AccessMixin(StaffServiceBase):
    async def set_access(
        self,
        business_account_id: int,
        staff_id: int,
        body: StaffAccessWrite,
    ) -> StaffMemberRead:
        async with self._session_factory() as session:
            profile = await self._business_profile(session, business_account_id)
            member = await self._owned_member(
                session, business_account_id, staff_id, lock=True
            )
            login = body.login.strip().casefold()
            if body.can_login:
                if not LOGIN_RE.fullmatch(login):
                    raise ApiError(
                        422,
                        "staff_login_invalid",
                        "Login 3–20 belgi bo‘lsin, kichik lotin harfi bilan boshlansin.",
                    )
                if await self._repository.duplicate_login(
                    session,
                    business_account_id=business_account_id,
                    login=login,
                    excluding_staff_id=member.id,
                ):
                    raise ApiError(409, "staff_login_taken", "Bu xodim logini band.")
                if not member.password_hash and not body.password:
                    raise ApiError(
                        422,
                        "staff_password_required",
                        "Xodim uchun yangi parol kiriting.",
                    )
            if body.password and len(body.password) < 8:
                raise ApiError(
                    422,
                    "staff_password_too_short",
                    "Parol kamida 8 belgi bo‘lsin.",
                )

            now = self._now()
            password_changed = bool(body.password)
            member.login = login or None
            member.can_login = body.can_login
            member.permissions = clean_permissions(
                body.permissions, str(profile.direction or "")
            )
            if password_changed:
                member.password_hash = hash_password(body.password)
            member.updated_at = now
            if not body.can_login or password_changed:
                await self._repository.revoke_staff_sessions(
                    session, staff_id=member.id, now=now
                )
            await session.commit()
            return self._member_read(member)

    async def set_schedule(
        self,
        business_account_id: int,
        staff_id: int,
        body: StaffScheduleWrite,
    ) -> StaffMemberRead:
        async with self._session_factory() as session:
            member = await self._owned_member(
                session, business_account_id, staff_id, lock=True
            )
            schedule: dict[str, dict[str, object]] = {}
            for index in range(7):
                key = f"d{index}"
                day = body.schedule.get(key)
                if day is None:
                    schedule[key] = {"on": False, "start": "", "end": ""}
                    continue
                if day.on and (not day.start or not day.end or day.start >= day.end):
                    raise ApiError(
                        422,
                        "staff_schedule_invalid",
                        "Ish kuni boshlanish va tugash vaqtini to‘g‘ri kiriting.",
                    )
                schedule[key] = day.model_dump()
            member.schedule = schedule
            member.updated_at = self._now()
            await session.commit()
            return self._member_read(member)

    async def add_profession(
        self,
        business_account_id: int,
        name: str,
    ) -> list[str]:
        clean = name.strip()
        if not clean:
            raise ApiError(422, "staff_profession_required", "Lavozim nomini kiriting.")
        async with self._session_factory() as session:
            await self._business_profile(session, business_account_id)
            if clean.casefold() not in {
                value.casefold() for value in DEFAULT_PROFESSIONS
            }:
                if not await self._repository.profession_exists(
                    session,
                    business_account_id=business_account_id,
                    name=clean,
                ):
                    session.add(
                        StaffProfession(
                            business_account_id=business_account_id,
                            name=clean,
                            created_at=self._now(),
                        )
                    )
                    try:
                        await session.commit()
                    except IntegrityError:
                        await session.rollback()
            return await self._profession_names(session, business_account_id)
