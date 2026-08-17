"""Xodimlar: qoshish, tahrirlash, holat, ochirish."""

from __future__ import annotations

from app.accounts.model import Account
from app.staff.model import StaffMember
from app.staff.permissions import (
    permission_definitions,
    permission_templates,
)
from app.staff.schemas import (
    StaffMemberCreate,
    StaffMemberPatch,
    StaffMemberRead,
    StaffPermissionRead,
    StaffSetupRead,
    StaffTemplateRead,
)
from app.staff.service_parts.base import StaffServiceBase


class MembersMixin(StaffServiceBase):
    async def setup(self, business_account_id: int) -> StaffSetupRead:
        async with self._session_factory() as session:
            profile = await self._business_profile(session, business_account_id)
            account = await session.get(Account, business_account_id)
            rows = await self._repository.members(session, business_account_id)
            professions = await self._profession_names(session, business_account_id)
            active = [self._member_read(row) for row in rows if row.status == "active"]
            fired = [self._member_read(row) for row in rows if row.status == "fired"]
            definitions = permission_definitions(profile.direction)
            templates = permission_templates(profile.direction)
            result = StaffSetupRead(
                active=active,
                fired=fired,
                active_count=len(active),
                fired_count=len(fired),
                total_salary=sum(row.salary for row in rows if row.status == "active"),
                firm_login=str(account.login if account else ""),
                business_direction=str(profile.direction or ""),
                professions=professions,
                permission_definitions=[
                    StaffPermissionRead(key=item.key, label=item.label, icon=item.icon)
                    for item in definitions
                ],
                permission_templates=[
                    StaffTemplateRead(
                        key=item.key,
                        label=item.label,
                        permissions=list(item.permissions),
                    )
                    for item in templates
                ],
            )
            await session.rollback()
            return result

    async def create_member(
        self,
        business_account_id: int,
        body: StaffMemberCreate,
    ) -> StaffMemberRead:
        async with self._session_factory() as session:
            await self._business_profile(session, business_account_id)
            now = self._now()
            member = StaffMember(
                business_account_id=business_account_id,
                legacy_source_id=None,
                name=body.name.strip(),
                profession=body.profession.strip(),
                phone=body.phone.strip(),
                salary=body.salary,
                hire_date=body.hire_date,
                status="active",
                note=body.note.strip(),
                login=None,
                password_hash=None,
                can_login=False,
                permissions=[],
                schedule={},
                created_at=now,
                updated_at=now,
                fired_at=None,
            )
            session.add(member)
            await session.commit()
            return self._member_read(member)

    async def update_member(
        self,
        business_account_id: int,
        staff_id: int,
        body: StaffMemberPatch,
    ) -> StaffMemberRead:
        async with self._session_factory() as session:
            member = await self._owned_member(
                session, business_account_id, staff_id, lock=True
            )
            values = body.model_dump(exclude_unset=True)
            for name, value in values.items():
                if isinstance(value, str):
                    value = value.strip()
                setattr(member, name, value)
            member.updated_at = self._now()
            await session.commit()
            return self._member_read(member)

    async def set_status(
        self,
        business_account_id: int,
        staff_id: int,
        status: str,
    ) -> StaffMemberRead:
        async with self._session_factory() as session:
            member = await self._owned_member(
                session, business_account_id, staff_id, lock=True
            )
            now = self._now()
            member.status = status
            member.fired_at = now if status == "fired" else None
            member.updated_at = now
            if status == "fired":
                await self._repository.revoke_staff_sessions(
                    session, staff_id=member.id, now=now
                )
                await self._repository.deactivate_queue_providers(
                    session,
                    business_account_id=business_account_id,
                    staff_id=member.id,
                    now=now,
                )
            await session.commit()
            return self._member_read(member)

    async def delete_member(self, business_account_id: int, staff_id: int) -> None:
        async with self._session_factory() as session:
            member = await self._owned_member(
                session, business_account_id, staff_id, lock=True
            )
            now = self._now()
            await self._repository.revoke_staff_sessions(
                session, staff_id=member.id, now=now
            )
            await self._repository.deactivate_queue_providers(
                session,
                business_account_id=business_account_id,
                staff_id=member.id,
                now=now,
            )
            await session.delete(member)
            await session.commit()

    async def active_member_rows(
        self,
        business_account_id: int,
    ) -> list[dict[str, object]]:
        async with self._session_factory() as session:
            rows = await self._repository.members(
                session, business_account_id, active_only=True
            )
            result = [
                {"id": row.id, "name": row.name, "profession": row.profession}
                for row in rows
            ]
            await session.rollback()
            return result
