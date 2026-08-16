"""O'quv guruhlari: ro'yxat, yaratish, tahrirlash, o'chirish."""

from __future__ import annotations

from app.education.management.base import EducationManagementServiceBase
from app.education.schemas import (
    EducationCreated,
    EducationGroupRead,
    EducationGroupWrite,
    EducationUpdated,
)


class GroupsMixin(EducationManagementServiceBase):
    async def list_groups(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
    ) -> list[EducationGroupRead]:
        self._require_any_education(permissions)
        async with self._session_factory() as session:
            profile = await self._require_scope(session, business_account_id)
            result = await self._groups_in_session(
                session,
                business_account_id=business_account_id,
                profile=profile,
            )
            await session.rollback()
            return result

    async def create_group(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        body: EducationGroupWrite,
    ) -> EducationCreated:
        self._require_permission(permissions, "education_groups")
        now = self._now_provider()
        async with self._session_factory() as session:
            try:
                profile = await self._require_scope(session, business_account_id)
                group_id = await self._cabinet.create_group_in_session(
                    session,
                    business_account_id=business_account_id,
                    profile=profile,
                    data=body.model_dump(),
                    now=int(now.timestamp()),
                )
                await session.commit()
                return EducationCreated(id=group_id)
            except Exception:
                await session.rollback()
                raise

    async def update_group(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        group_id: int,
        body: EducationGroupWrite,
    ) -> EducationUpdated:
        self._require_permission(permissions, "education_groups")
        now = self._now_provider()
        async with self._session_factory() as session:
            try:
                profile = await self._require_scope(session, business_account_id)
                await self._cabinet.update_group_in_session(
                    session,
                    business_account_id=business_account_id,
                    profile=profile,
                    group_id=group_id,
                    data=body.model_dump(),
                    now=int(now.timestamp()),
                )
                await session.commit()
                return EducationUpdated()
            except Exception:
                await session.rollback()
                raise

    async def delete_group(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        group_id: int,
    ) -> None:
        self._require_permission(permissions, "education_groups")
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                await self._cabinet.delete_group_in_session(
                    session,
                    business_account_id=business_account_id,
                    group_id=group_id,
                    now=int(self._now_provider().timestamp()),
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
