"""Foydalanuvchi shikoyati.

Bu yagona moderatsiya endpointi oddiy foydalanuvchi sessiyasi bilan
ishlaydi — shikoyatni admin emas, mijoz yuboradi. Qaror qabul qilish
esa `/api/v1/admin/reports/...` ostida.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.admin.reports_service import AdminReportsService
from app.admin.schemas import ReportCreate, ReportRow
from app.auth.dependencies import CurrentAccount, require_csrf


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])
CurrentWrite = Annotated[CurrentAccount, Depends(require_csrf)]


def reports_service(request: Request) -> AdminReportsService:
    return request.app.state.admin_reports_service


ServiceDep = Annotated[AdminReportsService, Depends(reports_service)]


@router.post("", response_model=ReportRow, status_code=status.HTTP_201_CREATED)
async def create_report(
    body: ReportCreate,
    current: CurrentWrite,
    service: ServiceDep,
) -> ReportRow:
    return ReportRow(**await service.create_report(
        reporter_account_id=current.account_id,
        content_kind=body.content_kind,
        content_id=body.content_id,
        reason_code=body.reason_code,
        comment=body.comment,
    ))
