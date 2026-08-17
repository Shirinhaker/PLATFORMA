"""Audit jurnali va uni CSV ga chiqarish."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.admin.dependencies import CurrentAdmin
from app.admin.router_parts.constants import (
    ReportId,
    ReportsDep,
)
from app.admin.schemas import (
    AuditDetail,
    AuditRow,
)

router = APIRouter()


@router.get("/audit", response_model=list[AuditRow])
async def admin_audit(
    admin: CurrentAdmin,
    service: ReportsDep,
    action: Annotated[str, Query(max_length=80)] = "",
) -> list[AuditRow]:
    del admin
    rows = await service.list_audit(action=action)
    return [AuditRow(**row) for row in rows]


@router.get("/audit/export.csv")
async def admin_audit_export(
    admin: CurrentAdmin,
    service: ReportsDep,
    action: Annotated[str, Query(max_length=80)] = "",
) -> Response:
    del admin
    return Response(
        content=await service.audit_csv(action=action),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="admin-audit.csv"',
            "Cache-Control": "no-store, private",
        },
    )


@router.get("/audit/{audit_id}", response_model=AuditDetail)
async def admin_audit_detail(
    audit_id: ReportId,
    admin: CurrentAdmin,
    service: ReportsDep,
) -> AuditDetail:
    del admin
    return AuditDetail(**await service.audit_detail(audit_id))
