from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.accounts.model import AccountType
from app.auth.dependencies import (
    CurrentAccount,
    require_business_owner,
    require_csrf,
    require_current_account,
)
from app.auth.router import _client_ip, _enforce_rate_limit, _set_session_cookie
from app.auth.security import sha256_token
from app.core.errors import ApiError
from app.staff.schemas import (
    StaffAccessWrite,
    StaffAttendanceRead,
    StaffAttendanceWrite,
    StaffLoginWrite,
    StaffMemberCreate,
    StaffMemberPatch,
    StaffMemberRead,
    StaffProfessionCreate,
    StaffProfessionsRead,
    StaffScheduleWrite,
    StaffSetupRead,
)
from app.staff.service import StaffService, UZBEKISTAN_TZ


router = APIRouter(prefix="/api/v1", tags=["staff"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]


def staff_service(request: Request) -> StaffService:
    return request.app.state.staff_service


StaffServiceDep = Annotated[StaffService, Depends(staff_service)]


def owner_account_id(current: CurrentAccount) -> int:
    require_business_owner(current)
    return current.account_id


@router.post("/staff-auth/login")
async def staff_login(
    body: StaffLoginWrite,
    request: Request,
    response: Response,
    service: StaffServiceDep,
):
    await _enforce_rate_limit(
        request,
        f"auth:staff:login:ip:{_client_ip(request)}",
        5,
        10 * 60,
    )
    await _enforce_rate_limit(
        request,
        "auth:staff:login:identity:"
        + sha256_token(f"{body.firm_login.casefold()}:{body.login.casefold()}"),
        5,
        10 * 60,
    )
    raw_token, identity = await service.login(
        body.firm_login,
        body.login,
        body.password,
    )
    _set_session_cookie(response, request, raw_token)
    return identity


@router.get("/staff", response_model=StaffSetupRead)
async def staff_setup(
    current: CurrentRead,
    service: StaffServiceDep,
) -> StaffSetupRead:
    return await service.setup(owner_account_id(current))


@router.post(
    "/staff",
    response_model=StaffMemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_staff_member(
    body: StaffMemberCreate,
    current: CurrentWrite,
    service: StaffServiceDep,
) -> StaffMemberRead:
    return await service.create_member(owner_account_id(current), body)


@router.post("/staff/professions", response_model=StaffProfessionsRead)
async def create_staff_profession(
    body: StaffProfessionCreate,
    current: CurrentWrite,
    service: StaffServiceDep,
) -> StaffProfessionsRead:
    professions = await service.add_profession(owner_account_id(current), body.name)
    return StaffProfessionsRead(professions=professions)


@router.get("/staff/attendance", response_model=StaffAttendanceRead)
async def staff_attendance(
    current: CurrentRead,
    service: StaffServiceDep,
    day: date | None = None,
) -> StaffAttendanceRead:
    selected = day or datetime.now(UZBEKISTAN_TZ).date()
    return await service.attendance(owner_account_id(current), selected)


@router.put("/staff/{staff_id}", response_model=StaffMemberRead)
async def update_staff_member(
    staff_id: int,
    body: StaffMemberPatch,
    current: CurrentWrite,
    service: StaffServiceDep,
) -> StaffMemberRead:
    return await service.update_member(owner_account_id(current), staff_id, body)


@router.post("/staff/{staff_id}/fire", response_model=StaffMemberRead)
async def fire_staff_member(
    staff_id: int,
    current: CurrentWrite,
    service: StaffServiceDep,
) -> StaffMemberRead:
    return await service.set_status(owner_account_id(current), staff_id, "fired")


@router.post("/staff/{staff_id}/rehire", response_model=StaffMemberRead)
async def rehire_staff_member(
    staff_id: int,
    current: CurrentWrite,
    service: StaffServiceDep,
) -> StaffMemberRead:
    return await service.set_status(owner_account_id(current), staff_id, "active")


@router.delete("/staff/{staff_id}", status_code=204)
async def delete_staff_member(
    staff_id: int,
    current: CurrentWrite,
    service: StaffServiceDep,
) -> Response:
    await service.delete_member(owner_account_id(current), staff_id)
    return Response(status_code=204)


@router.put("/staff/{staff_id}/access", response_model=StaffMemberRead)
async def update_staff_access(
    staff_id: int,
    body: StaffAccessWrite,
    current: CurrentWrite,
    service: StaffServiceDep,
) -> StaffMemberRead:
    return await service.set_access(owner_account_id(current), staff_id, body)


@router.put("/staff/{staff_id}/schedule", response_model=StaffMemberRead)
async def update_staff_schedule(
    staff_id: int,
    body: StaffScheduleWrite,
    current: CurrentWrite,
    service: StaffServiceDep,
) -> StaffMemberRead:
    return await service.set_schedule(owner_account_id(current), staff_id, body)


@router.put("/staff/{staff_id}/attendance", response_model=StaffAttendanceRead)
async def update_staff_attendance(
    staff_id: int,
    body: StaffAttendanceWrite,
    current: CurrentWrite,
    service: StaffServiceDep,
) -> StaffAttendanceRead:
    return await service.set_attendance(owner_account_id(current), staff_id, body)
