from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from copy import deepcopy
import time
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import AccountType
from app.cabinet_records.dual_write import sync_json_fallback
from app.core.errors import ApiError
from app.education.repository import EducationEnrollmentRepository
from app.education.schemas import CourseEnrollmentCreate, CourseEnrollmentCreated


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class EnrollmentRepository(Protocol):
    async def user_profile(self, session, account_id: int): ...

    async def locked_course_context(self, session, public_id: str): ...

    async def legacy_id(
        self,
        session,
        entity_type: str,
        target_id: int,
    ) -> int | None: ...

    async def resource_rows(
        self,
        session,
        profile,
        resource: str,
    ) -> list[dict[str, Any]]: ...

    async def replace_resource(
        self,
        session,
        *,
        account_id: int,
        resource: str,
        rows: list[dict[str, Any]],
    ) -> None: ...


class EducationEnrollmentService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        repository: EnrollmentRepository | None = None,
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
        if account_type is not AccountType.USER:
            raise ApiError(
                403,
                "education_user_required",
                "Avval oddiy profilga o'ting.",
            )

        async with self._session_factory() as session:
            customer = await self._repository.user_profile(session, account_id)
            if customer is None:
                raise ApiError(
                    404,
                    "course_enrollment_customer_not_found",
                    "Profil topilmadi.",
                )
            context = await self._repository.locked_course_context(
                session,
                body.course_item_public_id,
            )
            if context is None:
                raise ApiError(
                    404,
                    "course_not_found",
                    "Kurs topilmadi.",
                )
            course, business = context
            items = await self._repository.resource_rows(
                session,
                business,
                "items",
            )
            course_row = _course_row(items, str(course.source_record_key or ""))
            course_id = _integer(course_row.get("id")) if course_row else 0
            if course_row is None or course_id < 1:
                raise ApiError(
                    404,
                    "course_not_found",
                    "Kurs topilmadi.",
                )
            if str(course_row.get("enrollment_status") or "open") == "closed":
                raise ApiError(
                    400,
                    "course_enrollment_closed",
                    "Bu kursga qabul yopilgan.",
                )

            legacy_user_id = await self._repository.legacy_id(
                session,
                "user_account",
                account_id,
            )
            enrollments = await self._repository.resource_rows(
                session,
                business,
                "education_enrollments",
            )
            if _active_duplicate(
                enrollments,
                course_id=course_id,
                account_id=account_id,
                legacy_user_id=legacy_user_id,
            ):
                raise ApiError(
                    400,
                    "course_enrollment_duplicate",
                    "Siz bu kursga avval yozilgansiz.",
                )

            phone = str(body.phone or customer.phone or "").strip()[:30]
            if not phone:
                raise ApiError(
                    400,
                    "course_enrollment_phone_required",
                    "Telefon raqamini kiriting.",
                )
            legacy_business_id = await self._repository.legacy_id(
                session,
                "business_account",
                business.account_id,
            )
            enrollment_id = _next_id(enrollments)
            now = self._now()
            row = {
                "id": enrollment_id,
                "business_id": legacy_business_id or business.account_id,
                "course_item_id": course_id,
                "user_id": legacy_user_id or account_id,
                "user_account_id": account_id,
                "user_legacy_id": legacy_user_id or 0,
                "customer_name": str(customer.name or "O'quvchi")[:160],
                "phone": phone,
                "note": str(body.note or "").strip()[:300],
                "status": "new",
                "created_at": now,
                "updated_at": now,
            }
            enrollments.append(row)
            await self._repository.replace_resource(
                session,
                account_id=business.account_id,
                resource="education_enrollments",
                rows=enrollments,
            )
            payload = (
                dict(business.cabinet_payload)
                if isinstance(business.cabinet_payload, dict)
                else {}
            )
            payload["education_enrollments"] = deepcopy(enrollments)
            sync_json_fallback(business, payload)
            await session.commit()
            return CourseEnrollmentCreated(id=enrollment_id)


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


def _active_duplicate(
    rows: list[dict[str, Any]],
    *,
    course_id: int,
    account_id: int,
    legacy_user_id: int | None,
) -> bool:
    for row in rows:
        if _integer(row.get("course_item_id")) != course_id:
            continue
        if str(row.get("status") or "") not in {"new", "accepted"}:
            continue
        if _integer(row.get("user_account_id")) == account_id:
            return True
        if legacy_user_id is not None and _integer(row.get("user_id")) == legacy_user_id:
            return True
    return False


def _next_id(rows: list[dict[str, Any]]) -> int:
    return max((_integer(row.get("id")) for row in rows), default=0) + 1


def _integer(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
