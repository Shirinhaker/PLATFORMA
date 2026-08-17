"""Umumiy asos: biznes profili, egalik, xodim javobi."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import AccountType
from app.auth.schemas import SessionIdentity
from app.auth.security import (
    derive_csrf,
)
from app.core.config import Settings
from app.core.errors import ApiError
from app.staff.model import StaffMember
from app.staff.permissions import (
    clean_permissions,
)
from app.staff.repository import StaffRepository
from app.staff.schemas import (
    StaffMemberRead,
)
from app.staff.service_parts.helpers import (
    DEFAULT_PROFESSIONS,
    NowProvider,
    SessionFactory,
)


class StaffServiceBase:
    def __init__(
        self,
        session_factory: SessionFactory,
        settings: Settings,
        *,
        repository: StaffRepository | None = None,
        now_provider: NowProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._repository = repository or StaffRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def _business_profile(self, session: AsyncSession, account_id: int):
        profile = await self._repository.business_profile(session, account_id)
        if profile is None:
            raise ApiError(
                404,
                "business_profile_not_found",
                "Biznes profil topilmadi.",
            )
        return profile

    async def _owned_member(
        self,
        session: AsyncSession,
        business_account_id: int,
        staff_id: int,
        *,
        lock: bool,
    ) -> StaffMember:
        member = await self._repository.member(
            session,
            staff_id=staff_id,
            business_account_id=business_account_id,
            lock=lock,
        )
        if member is None:
            raise ApiError(404, "staff_not_found", "Xodim topilmadi.")
        return member

    async def _profession_names(
        self,
        session: AsyncSession,
        business_account_id: int,
    ) -> list[str]:
        custom = await self._repository.professions(session, business_account_id)
        result = list(DEFAULT_PROFESSIONS)
        seen = {value.casefold() for value in result}
        for row in custom:
            if row.name.casefold() not in seen:
                result.append(row.name)
                seen.add(row.name.casefold())
        return result

    def _member_read(self, member: StaffMember) -> StaffMemberRead:
        return StaffMemberRead(
            id=member.id,
            name=member.name,
            profession=member.profession,
            phone=member.phone,
            salary=member.salary,
            hire_date=member.hire_date,
            status=member.status,
            note=member.note,
            login=member.login or "",
            can_login=member.can_login,
            has_password=bool(member.password_hash),
            permissions=clean_permissions(member.permissions),
            schedule=member.schedule if isinstance(member.schedule, dict) else {},
            created_at=member.created_at,
            fired_at=member.fired_at,
        )

    def _identity(
        self,
        raw_token: str,
        member: StaffMember,
        expires_at: datetime,
    ) -> SessionIdentity:
        return SessionIdentity(
            account_id=member.business_account_id,
            account_type=AccountType.BUSINESS,
            login=member.login or "",
            name=member.name,
            csrf_token=derive_csrf(raw_token, self._settings.csrf_secret),
            expires_at=expires_at,
            actor_type="staff",
            staff_id=member.id,
            permissions=clean_permissions(member.permissions),
        )

    @staticmethod
    def _invalid_credentials() -> ApiError:
        return ApiError(
            401,
            "staff_invalid_credentials",
            "Firma logini, xodim logini yoki parol noto‘g‘ri.",
        )

    def _now(self) -> datetime:
        value = self._now_provider()
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
