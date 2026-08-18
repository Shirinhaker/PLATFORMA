"""Shikoyatlar: ro'yxat, tayinlash, hal qilish."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.admin.dependencies import CurrentAdmin
from app.admin.router_parts.constants import (
    ReportId,
    ReportsDep,
)
from app.admin.router_parts.deps import (
    _meta,
)
from app.admin.schemas import (
    ReportDecision,
    ReportRow,
)

router = APIRouter()


@router.get("/reports", response_model=list[ReportRow])
async def admin_reports(
    admin: CurrentAdmin,
    service: ReportsDep,
    status: Annotated[str, Query(max_length=20)] = "",
) -> list[ReportRow]:
    del admin
    rows = await service.list_reports(status=status)
    return [ReportRow(**row) for row in rows]


@router.get("/reports/{report_id}", response_model=ReportRow)
async def admin_report_detail(
    report_id: ReportId,
    admin: CurrentAdmin,
    service: ReportsDep,
) -> ReportRow:
    del admin
    return ReportRow(**await service.report_detail(report_id))


@router.post("/reports/{report_id}/assign", response_model=ReportRow)
async def admin_assign_report(
    report_id: ReportId,
    request: Request,
    admin: CurrentAdmin,
    service: ReportsDep,
) -> ReportRow:
    return ReportRow(
        **await service.assign(
            report_id=report_id, admin_tg_id=admin, meta=_meta(request)
        )
    )


@router.post("/reports/{report_id}/resolve", response_model=ReportRow)
async def admin_resolve_report(
    report_id: ReportId,
    body: ReportDecision,
    request: Request,
    admin: CurrentAdmin,
    service: ReportsDep,
) -> ReportRow:
    return ReportRow(
        **await service.decide(
            report_id=report_id,
            decision="resolved",
            resolution=body.resolution,
            admin_tg_id=admin,
            meta=_meta(request),
        )
    )


@router.post("/reports/{report_id}/dismiss", response_model=ReportRow)
async def admin_dismiss_report(
    report_id: ReportId,
    body: ReportDecision,
    request: Request,
    admin: CurrentAdmin,
    service: ReportsDep,
) -> ReportRow:
    return ReportRow(
        **await service.decide(
            report_id=report_id,
            decision="dismissed",
            resolution=body.resolution,
            admin_tg_id=admin,
            meta=_meta(request),
        )
    )
