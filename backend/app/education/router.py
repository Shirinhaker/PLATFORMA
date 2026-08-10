from typing import Annotated

from datetime import date

from fastapi import APIRouter, Depends, Query, Request, Response, status

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
    EducationAttendanceRead,
    EducationAttendanceSaved,
    EducationAttendanceWrite,
    EducationGroupRead,
    EducationPaymentControlRead,
    EducationPaymentCreate,
    EducationPaymentCreated,
    EducationPaymentMonthRead,
    EducationPaymentVoid,
    EducationPaymentVoided,
    EducationPayrollCreate,
    EducationPayrollCreated,
    EducationPayrollRead,
    EducationStatisticsReportRead,
    EducationTeacherCreated,
    EducationTeacherRead,
    EducationTeacherUpdated,
    EducationTeacherWrite,
)
from app.education.management_service import EducationManagementService
from app.education.service import EducationEnrollmentService
from app.education.statistics_service import EducationStatisticsService


router = APIRouter(prefix="/api/v1/education", tags=["education"])
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]


def service(request: Request) -> EducationEnrollmentService:
    return request.app.state.education_enrollment_service


def statistics_service(request: Request) -> EducationStatisticsService:
    return request.app.state.education_statistics_service


def management_service(request: Request) -> EducationManagementService:
    return request.app.state.education_management_service


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


@router.get("/groups", response_model=list[EducationGroupRead])
async def get_education_groups(
    current: CurrentRead,
    request: Request,
) -> list[EducationGroupRead]:
    return await management_service(request).list_groups(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
    )


@router.get("/attendance", response_model=EducationAttendanceRead)
async def get_education_attendance(
    current: CurrentRead,
    request: Request,
    group_id: Annotated[int, Query(gt=0)],
    lesson_date: Annotated[date, Query()],
) -> EducationAttendanceRead:
    return await management_service(request).attendance(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        group_id=group_id,
        lesson_date=lesson_date,
    )


@router.put("/attendance", response_model=EducationAttendanceSaved)
async def save_education_attendance(
    body: EducationAttendanceWrite,
    current: CurrentWrite,
    request: Request,
) -> EducationAttendanceSaved:
    return await management_service(request).save_attendance(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        body=body,
    )


@router.get("/payment-control", response_model=EducationPaymentControlRead)
async def get_education_payment_control(
    current: CurrentRead,
    request: Request,
    group_id: Annotated[int, Query(ge=0)] = 0,
) -> EducationPaymentControlRead:
    return await management_service(request).payment_control(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        group_id=group_id,
    )


@router.get("/payments", response_model=EducationPaymentMonthRead)
async def get_education_payments(
    current: CurrentRead,
    request: Request,
    payment_month: Annotated[str, Query(min_length=7, max_length=7)],
    group_id: Annotated[int, Query(ge=0)] = 0,
) -> EducationPaymentMonthRead:
    return await management_service(request).payments(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        payment_month=payment_month,
        group_id=group_id,
    )


@router.post(
    "/payments",
    response_model=EducationPaymentCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_education_payment(
    body: EducationPaymentCreate,
    current: CurrentWrite,
    request: Request,
) -> EducationPaymentCreated:
    return await management_service(request).create_payment(
        business_account_id=_business_id(current),
        actor_staff_id=current.staff_id,
        permissions=_permissions(current),
        body=body,
    )


@router.post(
    "/payments/{payment_id}/void",
    response_model=EducationPaymentVoided,
)
async def void_education_payment(
    payment_id: int,
    body: EducationPaymentVoid,
    current: CurrentWrite,
    request: Request,
) -> EducationPaymentVoided:
    return await management_service(request).void_payment(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        payment_id=payment_id,
        body=body,
    )


@router.get("/teachers", response_model=list[EducationTeacherRead])
async def get_education_teachers(
    current: CurrentRead,
    request: Request,
) -> list[EducationTeacherRead]:
    return await management_service(request).list_teachers(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
    )


@router.post(
    "/teachers",
    response_model=EducationTeacherCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_education_teacher(
    body: EducationTeacherWrite,
    current: CurrentWrite,
    request: Request,
) -> EducationTeacherCreated:
    return await management_service(request).create_teacher(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        body=body,
    )


@router.put("/teachers/{teacher_id}", response_model=EducationTeacherUpdated)
async def update_education_teacher(
    teacher_id: int,
    body: EducationTeacherWrite,
    current: CurrentWrite,
    request: Request,
) -> EducationTeacherUpdated:
    return await management_service(request).update_teacher(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        teacher_id=teacher_id,
        body=body,
    )


@router.delete("/teachers/{teacher_id}", status_code=204)
async def delete_education_teacher(
    teacher_id: int,
    current: CurrentWrite,
    request: Request,
) -> Response:
    await management_service(request).delete_teacher(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        teacher_id=teacher_id,
    )
    return Response(status_code=204)


@router.get("/teacher-payroll", response_model=EducationPayrollRead)
async def get_education_payroll(
    current: CurrentRead,
    request: Request,
    payment_month: Annotated[str, Query(min_length=7, max_length=7)],
) -> EducationPayrollRead:
    return await management_service(request).payroll(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        payment_month=payment_month,
    )


@router.post(
    "/teacher-payroll",
    response_model=EducationPayrollCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_education_payroll(
    body: EducationPayrollCreate,
    current: CurrentWrite,
    request: Request,
) -> EducationPayrollCreated:
    return await management_service(request).create_payroll(
        business_account_id=_business_id(current),
        actor_staff_id=current.staff_id,
        permissions=_permissions(current),
        body=body,
    )


@router.delete("/teacher-payroll/{payment_id}", status_code=204)
async def delete_education_payroll(
    payment_id: int,
    current: CurrentWrite,
    request: Request,
) -> Response:
    await management_service(request).delete_payroll(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        payment_id=payment_id,
    )
    return Response(status_code=204)


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
