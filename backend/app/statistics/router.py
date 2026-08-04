from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.accounts.model import AccountType
from app.auth.dependencies import CurrentAccount, require_current_account
from app.core.errors import ApiError
from app.statistics.schemas import StatisticsNavigationRead, StatisticsReportRead
from app.statistics.service import StatisticsService


router = APIRouter(prefix="/api/v1/statistics", tags=["statistics"])
CurrentRead = Annotated[CurrentAccount, Depends(require_current_account)]


def statistics_service(request: Request) -> StatisticsService:
    return request.app.state.statistics_service


StatisticsServiceDep = Annotated[StatisticsService, Depends(statistics_service)]


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


@router.get("", response_model=StatisticsReportRead)
async def get_statistics(
    current: CurrentRead,
    service: StatisticsServiceDep,
    period: Annotated[str, Query(max_length=16)] = "oy",
    anchor: Annotated[str, Query(max_length=10)] = "",
) -> StatisticsReportRead:
    return await service.report(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        period=period,
        anchor=anchor,
    )


@router.get("/nav", response_model=StatisticsNavigationRead)
async def navigate_statistics(
    current: CurrentRead,
    service: StatisticsServiceDep,
    period: Annotated[str, Query(max_length=16)] = "oy",
    anchor: Annotated[str, Query(max_length=10)] = "",
    direction: Annotated[int, Query(alias="dir")] = -1,
) -> StatisticsNavigationRead:
    return StatisticsNavigationRead(anchor=await service.navigation(
        business_account_id=_business_id(current),
        permissions=_permissions(current),
        period=period,
        anchor=anchor,
        direction=direction,
    ))
