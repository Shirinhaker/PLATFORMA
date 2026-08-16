"""O'qituvchilar: ro'yxat va kartochka."""

from __future__ import annotations

from app.core.errors import ApiError
from app.education.management.base import EducationManagementServiceBase
from app.education.management.helpers import (
    _teacher_read,
)
from app.education.model import (
    EducationTeacher,
)
from app.education.schemas import (
    EducationTeacherCreated,
    EducationTeacherRead,
    EducationTeacherUpdated,
    EducationTeacherWrite,
)


class TeachersMixin(EducationManagementServiceBase):
    async def list_teachers(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
    ) -> list[EducationTeacherRead]:
        self._require_permission(permissions, "education_teachers")
        async with self._session_factory() as session:
            await self._require_scope(session, business_account_id)
            rows = await self._repository.active_teachers(
                session,
                business_account_id=business_account_id,
            )
            result = [
                _teacher_read(teacher, group_count) for teacher, group_count in rows
            ]
            await session.rollback()
            return result

    async def create_teacher(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        body: EducationTeacherWrite,
    ) -> EducationTeacherCreated:
        self._require_permission(permissions, "education_teachers")
        now = self._now_provider()
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                teacher = EducationTeacher(
                    business_account_id=business_account_id,
                    legacy_source_id=None,
                    status="active",
                    created_at=now,
                    updated_at=now,
                    **body.model_dump(),
                )
                session.add(teacher)
                await session.flush()
                await session.commit()
                return EducationTeacherCreated(id=teacher.id)
            except Exception:
                await session.rollback()
                raise

    async def update_teacher(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        teacher_id: int,
        body: EducationTeacherWrite,
    ) -> EducationTeacherUpdated:
        self._require_permission(permissions, "education_teachers")
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                teacher = await self._repository.active_teacher(
                    session,
                    business_account_id=business_account_id,
                    teacher_id=teacher_id,
                    lock=True,
                )
                if teacher is None:
                    raise ApiError(
                        404, "education_teacher_not_found", "O'qituvchi topilmadi."
                    )
                for name, value in body.model_dump().items():
                    setattr(teacher, name, value)
                teacher.updated_at = self._now_provider()
                await self._repository.update_teacher_snapshot(
                    session,
                    business_account_id=business_account_id,
                    teacher_id=teacher.id,
                    full_name=teacher.full_name,
                )
                await session.commit()
                return EducationTeacherUpdated()
            except Exception:
                await session.rollback()
                raise

    async def delete_teacher(
        self,
        *,
        business_account_id: int,
        permissions: tuple[str, ...] | None,
        teacher_id: int,
    ) -> None:
        self._require_permission(permissions, "education_teachers")
        async with self._session_factory() as session:
            try:
                await self._require_scope(session, business_account_id)
                teacher = await self._repository.active_teacher(
                    session,
                    business_account_id=business_account_id,
                    teacher_id=teacher_id,
                    lock=True,
                )
                if teacher is None:
                    raise ApiError(
                        404, "education_teacher_not_found", "O'qituvchi topilmadi."
                    )
                teacher.status = "inactive"
                teacher.updated_at = self._now_provider()
                await self._repository.unlink_teacher(
                    session,
                    business_account_id=business_account_id,
                    teacher_id=teacher.id,
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
