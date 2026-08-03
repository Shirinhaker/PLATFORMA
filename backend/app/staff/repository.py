from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.profiles.model import BusinessProfile
from app.queues.model import QueueProvider
from app.staff.model import (
    StaffAttendance,
    StaffMember,
    StaffProfession,
    StaffSession,
)


class StaffRepository:
    async def business_profile(
        self,
        session: AsyncSession,
        account_id: int,
    ) -> BusinessProfile | None:
        return await session.get(BusinessProfile, account_id)

    async def business_account_by_login(
        self,
        session: AsyncSession,
        login: str,
    ) -> Account | None:
        return await session.scalar(
            select(Account)
            .where(
                Account.account_type == AccountType.BUSINESS,
                Account.status == "active",
                func.lower(Account.login) == login,
            )
            .limit(1)
        )

    async def members(
        self,
        session: AsyncSession,
        business_account_id: int,
        *,
        active_only: bool = False,
    ) -> list[StaffMember]:
        statement = select(StaffMember).where(
            StaffMember.business_account_id == business_account_id
        )
        if active_only:
            statement = statement.where(StaffMember.status == "active")
        statement = statement.order_by(
            StaffMember.status,
            func.lower(StaffMember.name),
            StaffMember.id,
        )
        return list((await session.scalars(statement)).all())

    async def member(
        self,
        session: AsyncSession,
        *,
        staff_id: int,
        business_account_id: int | None = None,
        lock: bool = False,
    ) -> StaffMember | None:
        statement = select(StaffMember).where(StaffMember.id == staff_id)
        if business_account_id is not None:
            statement = statement.where(
                StaffMember.business_account_id == business_account_id
            )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def member_by_login(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        login: str,
    ) -> StaffMember | None:
        return await session.scalar(
            select(StaffMember)
            .where(
                StaffMember.business_account_id == business_account_id,
                func.lower(StaffMember.login) == login,
            )
            .limit(1)
        )

    async def duplicate_login(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        login: str,
        excluding_staff_id: int,
    ) -> bool:
        return await session.scalar(
            select(StaffMember.id)
            .where(
                StaffMember.business_account_id == business_account_id,
                func.lower(StaffMember.login) == login,
                StaffMember.id != excluding_staff_id,
            )
            .limit(1)
        ) is not None

    async def professions(
        self,
        session: AsyncSession,
        business_account_id: int,
    ) -> list[StaffProfession]:
        return list((await session.scalars(
            select(StaffProfession)
            .where(StaffProfession.business_account_id == business_account_id)
            .order_by(func.lower(StaffProfession.name), StaffProfession.id)
        )).all())

    async def profession_exists(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        name: str,
    ) -> bool:
        return await session.scalar(
            select(StaffProfession.id)
            .where(
                StaffProfession.business_account_id == business_account_id,
                func.lower(StaffProfession.name) == name.casefold(),
            )
            .limit(1)
        ) is not None

    async def attendance_for_day(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        day: date,
    ) -> dict[int, StaffAttendance]:
        rows = (await session.scalars(
            select(StaffAttendance).where(
                StaffAttendance.business_account_id == business_account_id,
                StaffAttendance.date == day,
            )
        )).all()
        return {row.staff_id: row for row in rows}

    async def attendance_for_month(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        first_day: date,
        next_month: date,
    ) -> list[StaffAttendance]:
        return list((await session.scalars(
            select(StaffAttendance).where(
                StaffAttendance.business_account_id == business_account_id,
                StaffAttendance.date >= first_day,
                StaffAttendance.date < next_month,
            )
        )).all())

    async def attendance(
        self,
        session: AsyncSession,
        *,
        staff_id: int,
        day: date,
        lock: bool = False,
    ) -> StaffAttendance | None:
        statement = select(StaffAttendance).where(
            StaffAttendance.staff_id == staff_id,
            StaffAttendance.date == day,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def delete_attendance(
        self,
        session: AsyncSession,
        *,
        staff_id: int,
        day: date,
    ) -> None:
        await session.execute(
            delete(StaffAttendance).where(
                StaffAttendance.staff_id == staff_id,
                StaffAttendance.date == day,
            )
        )

    async def revoke_staff_sessions(
        self,
        session: AsyncSession,
        *,
        staff_id: int,
        now: datetime,
    ) -> None:
        await session.execute(
            update(StaffSession)
            .where(
                StaffSession.staff_id == staff_id,
                StaffSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

    async def deactivate_queue_providers(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        staff_id: int,
        now: datetime,
    ) -> None:
        await session.execute(
            update(QueueProvider)
            .where(
                QueueProvider.business_account_id == business_account_id,
                QueueProvider.legacy_staff_id == staff_id,
                QueueProvider.status == "active",
            )
            .values(status="inactive", updated_at=now)
        )

    async def session_by_token_hash(
        self,
        session: AsyncSession,
        *,
        token_hash: str,
        now: datetime,
        lock: bool = False,
    ) -> StaffSession | None:
        statement = select(StaffSession).where(
            StaffSession.token_hash == token_hash,
            StaffSession.revoked_at.is_(None),
            StaffSession.expires_at > now,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)
