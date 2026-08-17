"""Talim resurslarini relatsion jadvalga yozish."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.business_online.payload.helpers import (
    missing_record_id,
    unix_now,
)
from app.business_online.payload.spec import (
    display_resource_rows,
    ensure_resource_direction,
)
from app.business_online.service_parts.base import BusinessOnlineServiceBase
from app.business_online.service_parts.helpers import (
    _record_id,
)
from app.core.errors import ApiError
from app.education.repository import (
    GROUPS as EDUCATION_GROUPS,
)
from app.profiles.model import BusinessProfile


class EducationMixin(BusinessOnlineServiceBase):
    async def _education_write(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        resource: str,
        operation: str,
        record_id: int | str | None,
        data: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """Guruh/o'quvchi yozuvini relatsion jadvalga yo'naltiradi."""
        profile = await session.get(BusinessProfile, account_id)
        if profile is None:
            raise ApiError(
                404,
                "business_profile_not_found",
                "Biznes profil topilmadi.",
            )
        ensure_resource_direction(profile, resource)
        now = unix_now()
        target_id = None if record_id is None else _record_id(record_id)
        is_group = resource == EDUCATION_GROUPS

        if operation == "create":
            if is_group:
                target_id = await self._education_cabinet.create_group_in_session(
                    session,
                    business_account_id=account_id,
                    profile=profile,
                    data=data,
                    now=now,
                )
            else:
                target_id = await self._education_cabinet.create_student_in_session(
                    session,
                    business_account_id=account_id,
                    data=data,
                    now=now,
                )
        elif operation == "update":
            if is_group:
                await self._education_cabinet.update_group_in_session(
                    session,
                    business_account_id=account_id,
                    profile=profile,
                    group_id=target_id,
                    data=data,
                    now=now,
                )
            else:
                await self._education_cabinet.update_student_in_session(
                    session,
                    business_account_id=account_id,
                    student_id=target_id,
                    data=data,
                    now=now,
                )
        elif operation == "transfer":
            await self._education_cabinet.transfer_student_in_session(
                session,
                business_account_id=account_id,
                student_id=target_id,
                group_id=_record_id(data.get("group_id")),
                transfer_date=str(data.get("transfer_date") or ""),
                note=str(data.get("note") or ""),
                now=now,
            )
        else:
            if is_group:
                await self._education_cabinet.delete_group_in_session(
                    session,
                    business_account_id=account_id,
                    group_id=target_id,
                    now=now,
                )
            else:
                await self._education_cabinet.delete_student_in_session(
                    session,
                    business_account_id=account_id,
                    student_id=target_id,
                    now=now,
                )

        payload = await self._hybrid_payload(session, profile)
        displayed = display_resource_rows(payload, resource)
        item = next(
            (row for row in displayed if str(row.get("id")) == str(target_id)),
            None,
        )
        await session.commit()
        return deepcopy(item), deepcopy(displayed)

    async def _apply_enrollment_action(
        self,
        session: AsyncSession,
        *,
        account_id: int,
        resource: str,
        action: str,
        record_id: int | str | None,
        data: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """Ariza qabul qilish/rad etish — uch yozuv bitta tranzaksiyada."""
        profile = await session.get(BusinessProfile, account_id)
        if profile is None:
            raise ApiError(
                404,
                "business_profile_not_found",
                "Biznes profil topilmadi.",
            )
        ensure_resource_direction(profile, resource)
        if record_id is None:
            raise missing_record_id()
        try:
            enrollment_id = int(record_id)
        except (TypeError, ValueError):
            raise ApiError(
                404,
                "new_education_enrollment_not_found",
                "Yangi ariza topilmadi.",
            ) from None
        now = unix_now()
        if action == "accept":
            try:
                group_id = int(data.get("group_id") or 0)
            except (TypeError, ValueError):
                group_id = 0
            await self._education_service.accept_in_session(
                session,
                business_account_id=account_id,
                enrollment_id=enrollment_id,
                group_id=group_id,
                now=now,
            )
        else:
            await self._education_service.reject_in_session(
                session,
                business_account_id=account_id,
                enrollment_id=enrollment_id,
                now=now,
            )
        payload = await self._hybrid_payload(session, profile)
        displayed = display_resource_rows(payload, resource)
        item = next(
            (row for row in displayed if str(row.get("id")) == str(record_id)),
            None,
        )
        await session.commit()
        return deepcopy(item), deepcopy(displayed)
