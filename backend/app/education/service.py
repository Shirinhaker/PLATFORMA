from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
import time
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import AccountType
from app.core.errors import ApiError
from app.education.model import CourseEnrollment, EducationStudent
from app.education.repository import EducationEnrollmentRepository
from app.education.schemas import CourseEnrollmentCreate, CourseEnrollmentCreated


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class EducationEnrollmentService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: EducationEnrollmentRepository | None = None,
        now: Callable[[], int] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository or EducationEnrollmentRepository()
        self._now = now or (lambda: int(time.time()))

    async def create(
        self,
        *,
        account_id: int,
        account_type: AccountType,
        body: CourseEnrollmentCreate,
    ) -> CourseEnrollmentCreated:
        async with self._session_factory() as session:
            # v1656da kursga har qanday kirgan akkaunt yozila olardi. Yangi
            # modelda biznes alohida akkaunt, shuning uchun ariza uning
            # bog'langan oddiy profili nomidan yoziladi.
            student_account_id = account_id
            if account_type is not AccountType.USER:
                student_account_id = await self._repository.linked_user_account_id(
                    session,
                    business_account_id=account_id,
                )
                if student_account_id is None:
                    raise ApiError(
                        403,
                        "education_user_required",
                        "Avval oddiy profilga o'ting.",
                    )
            customer = await self._repository.user_profile(
                session,
                student_account_id,
            )
            if customer is None:
                raise ApiError(
                    404,
                    "course_enrollment_customer_not_found",
                    "Profil topilmadi.",
                )
            context = await self._repository.course_context(
                session,
                body.course_item_public_id,
            )
            if context is None:
                raise ApiError(404, "course_not_found", "Kurs topilmadi.")
            course, business = context
            items = await self._repository.catalog_rows(session, business)
            course_row = _course_row(items, str(course.source_record_key or ""))
            course_id = _integer(course_row.get("id")) if course_row else 0
            if course_row is None or course_id < 1:
                raise ApiError(404, "course_not_found", "Kurs topilmadi.")
            if str(course_row.get("enrollment_status") or "open") == "closed":
                raise ApiError(
                    400,
                    "course_enrollment_closed",
                    "Bu kursga qabul yopilgan.",
                )

            phone = str(body.phone or customer.phone or "").strip()[:30]
            if not phone:
                raise ApiError(
                    400,
                    "course_enrollment_phone_required",
                    "Telefon raqamini kiriting.",
                )
            legacy_user_id = await self._repository.legacy_id(
                session,
                "user_account",
                student_account_id,
            )
            legacy_business_id = await self._repository.legacy_id(
                session,
                "business_account",
                business.account_id,
            )
            now = self._now()
            enrollment = CourseEnrollment(
                business_account_id=business.account_id,
                legacy_source_id=None,
                legacy_business_id=legacy_business_id,
                course_item_id=course_id,
                user_account_id=student_account_id,
                legacy_user_id=legacy_user_id,
                customer_name=str(customer.name or "O'quvchi")[:160],
                phone=phone,
                note=str(body.note or "").strip()[:300],
                status="new",
                group_id=None,
                created_at=now,
                updated_at=now,
            )
            # Takroriy arizani baza to'sadi (qisman noyob indeks), shuning
            # uchun butun ro'yxatni o'qib skanerlash kerak emas.
            try:
                await self._repository.add_enrollment(session, enrollment)
            except IntegrityError as error:
                await session.rollback()
                raise ApiError(
                    400,
                    "course_enrollment_duplicate",
                    "Siz bu kursga avval yozilgansiz.",
                ) from error
            enrollment_id = enrollment.id
            await session.commit()
            return CourseEnrollmentCreated(id=enrollment_id)

    async def accept_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        enrollment_id: int,
        group_id: int,
        now: int,
    ) -> None:
        """Arizani qabul qiladi: guruh tekshiriladi, o'quvchi yoziladi.

        Uch yozuv ham chaqiruvchining tranzaksiyasida bajariladi —
        xato bo'lsa hammasi birga qaytariladi.
        """
        enrollment = await self._repository.enrollment(
            session,
            business_account_id=business_account_id,
            enrollment_id=enrollment_id,
            lock=True,
        )
        if enrollment is None or enrollment.status != "new":
            raise ApiError(
                404,
                "new_education_enrollment_not_found",
                "Yangi ariza topilmadi.",
            )
        group = await self._repository.group(
            session,
            business_account_id=business_account_id,
            group_id=group_id,
        )
        if group is None:
            raise ApiError(400, "education_group_required", "Guruhni tanlang.")
        if group.course_item_id and group.course_item_id != enrollment.course_item_id:
            raise ApiError(
                400,
                "education_group_course_mismatch",
                "Tanlangan guruh boshqa kursga tegishli.",
            )
        student = await self._repository.active_student(
            session,
            business_account_id=business_account_id,
            user_account_id=enrollment.user_account_id,
            legacy_user_id=enrollment.legacy_user_id,
        )
        if student is None:
            await self._repository.add_student(session, EducationStudent(
                business_account_id=business_account_id,
                legacy_source_id=None,
                group_id=group.id,
                user_account_id=enrollment.user_account_id,
                legacy_user_id=enrollment.legacy_user_id,
                full_name=enrollment.customer_name,
                phone=enrollment.phone,
                joined_date=_local_day(now),
                note=("Kurs arizasi: " + enrollment.note)[:500],
                monthly_fee=0,
                status="active",
                created_at=now,
                updated_at=now,
            ))
        else:
            student.group_id = group.id
            student.phone = enrollment.phone
            student.updated_at = now
        await self._repository.touch_enrollment(
            session,
            enrollment_id=enrollment.id,
            status="accepted",
            group_id=group.id,
            now=now,
        )

    async def reject_in_session(
        self,
        session: AsyncSession,
        *,
        business_account_id: int,
        enrollment_id: int,
        now: int,
    ) -> None:
        enrollment = await self._repository.enrollment(
            session,
            business_account_id=business_account_id,
            enrollment_id=enrollment_id,
            lock=True,
        )
        if enrollment is None or enrollment.status != "new":
            raise ApiError(
                404,
                "new_education_enrollment_not_found",
                "Yangi ariza topilmadi.",
            )
        await self._repository.touch_enrollment(
            session,
            enrollment_id=enrollment.id,
            status="rejected",
            group_id=None,
            now=now,
        )


def _local_day(now: int) -> str:
    from datetime import UTC, datetime, timedelta

    return (
        datetime.fromtimestamp(now, UTC) + timedelta(hours=5)
    ).strftime("%Y-%m-%d")


def _course_row(
    rows: list[dict[str, Any]],
    source_record_key: str,
) -> dict[str, Any] | None:
    candidates = {source_record_key}
    if source_record_key.startswith("item:"):
        candidates.add(source_record_key.removeprefix("item:"))
    return next(
        (row for row in rows if str(row.get("id") or "") in candidates),
        None,
    )


def _integer(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
