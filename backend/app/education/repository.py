from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import Account, AccountType
from app.cabinet_records.repository import CabinetRecordRepository
from app.catalog.model import CatalogItem
from app.education.model import (
    CourseEnrollment,
    EducationGroup,
    EducationStudent,
)
from app.legacy_migration.model import LegacyIdMap, ReviewState
from app.profiles.model import BusinessProfile, UserProfile


# Kabinet payloadidagi resurs nomlari — frontend shu nomlarni kutadi.
ENROLLMENTS = "education_enrollments"
GROUPS = "education_groups"
STUDENTS = "education_students"


def _enrollment_row(row: CourseEnrollment) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": row.id,
        "business_id": row.legacy_business_id or row.business_account_id,
        "course_item_id": row.course_item_id,
        "user_id": row.legacy_user_id or row.user_account_id or 0,
        "user_account_id": row.user_account_id or 0,
        "user_legacy_id": row.legacy_user_id or 0,
        "customer_name": row.customer_name,
        "phone": row.phone,
        "note": row.note,
        "status": row.status,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
    if row.group_id is not None:
        result["group_id"] = row.group_id
    return result


def _group_row(row: EducationGroup) -> dict[str, Any]:
    return {
        "id": row.id,
        "course_item_id": row.course_item_id or 0,
        "name": row.name,
        "teacher_id": row.teacher_id or 0,
        "status": row.status,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _student_row(row: EducationStudent) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": row.id,
        "group_id": row.group_id or 0,
        "user_id": row.legacy_user_id or row.user_account_id or 0,
        "full_name": row.full_name,
        "phone": row.phone,
        "joined_date": row.joined_date,
        "note": row.note,
        "monthly_fee": row.monthly_fee,
        "status": row.status,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
    if row.user_account_id:
        result["user_account_id"] = row.user_account_id
    return result


_PROJECTIONS = {
    ENROLLMENTS: (CourseEnrollment, _enrollment_row),
    GROUPS: (EducationGroup, _group_row),
    STUDENTS: (EducationStudent, _student_row),
}


class EducationEnrollmentRepository:
    def __init__(
        self,
        cabinet_records: CabinetRecordRepository | None = None,
    ) -> None:
        self._cabinet_records = cabinet_records or CabinetRecordRepository()

    @staticmethod
    def supported(session: AsyncSession) -> bool:
        return all(
            hasattr(session, name)
            for name in ("execute", "scalars", "scalar")
        )

    async def user_profile(
        self,
        session: AsyncSession,
        account_id: int,
    ) -> UserProfile | None:
        return await session.get(UserProfile, account_id)

    async def linked_user_account_id(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
    ) -> int | None:
        from app.profiles.model import ProfileLink

        value = await session.scalar(
            select(ProfileLink.user_account_id).where(
                ProfileLink.business_account_id == business_account_id,
            )
        )
        return int(value) if value is not None else None

    async def course_context(
        self,
        session: AsyncSession,
        public_id: str,
    ) -> tuple[CatalogItem, BusinessProfile] | None:
        """Kursni va uning o'quv markazini topadi.

        Bu yerda hech narsa qulflanmaydi: ariza endi alohida jadvalga
        bitta INSERT bilan yoziladi, shuning uchun o'quv markazining
        profil qatorini ushlab turishga hojat yo'q.
        """
        statement = (
            select(CatalogItem, BusinessProfile)
            .join(
                BusinessProfile,
                BusinessProfile.account_id == CatalogItem.business_account_id,
            )
            .join(Account, Account.id == BusinessProfile.account_id)
            .where(
                CatalogItem.public_id == public_id,
                CatalogItem.kind == "service",
                CatalogItem.status == "active",
                CatalogItem.review_state == ReviewState.READY,
                BusinessProfile.direction == "Ta'lim faoliyati",
                Account.status == "active",
                Account.account_type == AccountType.BUSINESS,
            )
            .limit(1)
        )
        row = (await session.execute(statement)).first()
        if row is None:
            return None
        return row[0], row[1]

    async def legacy_id(
        self,
        session: AsyncSession,
        entity_type: str,
        target_id: int,
    ) -> int | None:
        value = await session.scalar(
            select(LegacyIdMap.legacy_id)
            .where(
                LegacyIdMap.entity_type == entity_type,
                LegacyIdMap.target_id == target_id,
                LegacyIdMap.mapping_status == "mapped",
            )
            .order_by(LegacyIdMap.legacy_id)
            .limit(1)
        )
        return int(value) if value is not None else None

    async def list_rows(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        resource: str,
    ) -> list[dict[str, Any]] | None:
        """Kabinet payloadi uchun v1656 shaklidagi qatorlar."""
        projection = _PROJECTIONS.get(resource)
        if projection is None or not self.supported(session):
            return None
        model, to_row = projection
        rows = list((await session.scalars(
            select(model)
            .where(model.business_account_id == business_account_id)
            .order_by(model.id)
        )).all())
        return [to_row(row) for row in rows]

    async def catalog_rows(
        self,
        session: AsyncSession,
        profile: BusinessProfile,
    ) -> list[dict[str, Any]]:
        """Eski `items` resursi — kursning qabul holati shu yerda.

        Katalog hali kabinet payloadida; u alohida ko'chiriladi.
        """
        if await self._cabinet_records.has_resource(
            session,
            account_id=profile.account_id,
            account_type="business",
            resource="items",
        ):
            rows = await self._cabinet_records.read_resource(
                session,
                account_id=profile.account_id,
                account_type="business",
                resource="items",
            )
            return [dict(row) for row in rows if isinstance(row, dict)]
        payload = (
            profile.cabinet_payload
            if isinstance(profile.cabinet_payload, dict)
            else {}
        )
        rows = payload.get("items", [])
        if not isinstance(rows, list):
            return []
        return [dict(row) for row in rows if isinstance(row, dict)]

    async def add_enrollment(
        self,
        session: AsyncSession,
        enrollment: CourseEnrollment,
    ) -> None:
        session.add(enrollment)
        await session.flush()

    async def enrollment(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        enrollment_id: int,
        lock: bool = False,
    ) -> CourseEnrollment | None:
        statement = select(CourseEnrollment).where(
            CourseEnrollment.id == enrollment_id,
            CourseEnrollment.business_account_id == business_account_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def group(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        group_id: int,
    ) -> EducationGroup | None:
        return await session.scalar(
            select(EducationGroup).where(
                EducationGroup.id == group_id,
                EducationGroup.business_account_id == business_account_id,
                EducationGroup.status == "active",
            )
        )

    async def active_student(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        user_account_id: int | None,
        legacy_user_id: int | None,
    ) -> EducationStudent | None:
        """Arizachi allaqachon o'quvchi bo'lsa — o'sha yozuvni topadi."""
        conditions = []
        if user_account_id:
            conditions.append(
                EducationStudent.user_account_id == user_account_id
            )
        if legacy_user_id:
            conditions.append(
                EducationStudent.legacy_user_id == legacy_user_id
            )
        if not conditions:
            return None
        from sqlalchemy import or_

        return await session.scalar(
            select(EducationStudent)
            .where(
                EducationStudent.business_account_id == business_account_id,
                EducationStudent.status == "active",
                or_(*conditions),
            )
            .order_by(EducationStudent.id)
            .limit(1)
        )

    async def add_student(
        self,
        session: AsyncSession,
        student: EducationStudent,
    ) -> None:
        session.add(student)
        await session.flush()

    async def touch_enrollment(
        self,
        session: AsyncSession,
        *,
        enrollment_id: int,
        status: str,
        group_id: int | None,
        now: int,
    ) -> None:
        await session.execute(
            update(CourseEnrollment)
            .where(CourseEnrollment.id == enrollment_id)
            .values(status=status, group_id=group_id, updated_at=now)
        )
