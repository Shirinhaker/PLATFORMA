from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.accounts.model import AccountType
from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
    require_staff_permission,
)
from app.core.errors import ApiError
from app.education.schemas import (
    CourseEnrollmentCreate,
    CourseEnrollmentCreated,
    EducationStatisticsReportRead,
)
from app.education.service import EducationEnrollmentService
from app.education.statistics_service import EducationStatisticsService


router = APIRouter(prefix="/api/v1/education", tags=["education"])
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]


def service(request: Request) -> EducationEnrollmentService:
    return request.app.state.education_enrollment_service


def statistics_service(request: Request) -> EducationStatisticsService:
    return request.app.state.education_statistics_service


def _business_id(current: CurrentAccount) -> int:
    if current.account_type is not AccountType.BUSINESS:
        raise ApiError(
            403,
            "business_account_required",
            "Bu bo‘lim faqat biznes akkaunt uchun.",
        )
    return current.account_id


def _permissions(current: CurrentAccount) -> tuple[str, ...] | None:
    return current.permissions if current.actor_type == "staff" else None


@router.get("/statistics", response_model=EducationStatisticsReportRead)
async def get_education_statistics(
    current: CurrentRead,
    request: Request,
    period: Annotated[str, Query(max_length=12)] = "month",
    selected_date: Annotated[
        str,
        Query(alias="date", max_length=10),
    ] = "",
) -> EducationStatisticsReportRead:
    return await statistics_service(request).report(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        period=period,
        selected_date=selected_date,
    )


@router.post(
    "/enrollments",
    response_model=CourseEnrollmentCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_course_enrollment(
    body: CourseEnrollmentCreate,
    request: Request,
    current: CurrentWrite,
) -> CourseEnrollmentCreated:
    require_staff_permission(current, "__business_owner__")
    return await service(request).create(
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )
