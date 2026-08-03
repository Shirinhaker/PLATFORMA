from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.auth.dependencies import CurrentAccount, require_csrf
from app.education.schemas import CourseEnrollmentCreate, CourseEnrollmentCreated
from app.education.service import EducationEnrollmentService


router = APIRouter(prefix="/api/v1/education", tags=["education"])
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]


def service(request: Request) -> EducationEnrollmentService:
    return request.app.state.education_enrollment_service


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
    return await service(request).create(
        account_id=current.account_id,
        account_type=current.account_type,
        body=body,
    )
