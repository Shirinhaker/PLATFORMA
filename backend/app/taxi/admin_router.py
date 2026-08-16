from typing import Annotated

from fastapi import APIRouter, Path, Request

from app.admin.audit import request_meta
from app.admin.dependencies import CurrentAdmin
from app.taxi.schemas import AdminDriverRead, DriverTopupRead, DriverTopupWrite
from app.taxi.service import TaxiService

router = APIRouter(prefix="/api/v1/admin/taxi", tags=["admin", "taxi"])
DriverId = Annotated[int, Path(gt=0)]


def service(request: Request) -> TaxiService:
    return request.app.state.taxi_service


@router.get("/drivers", response_model=list[AdminDriverRead])
async def list_drivers(request: Request, admin: CurrentAdmin):
    del admin
    return await service(request).list_admin_drivers()


@router.post("/drivers/{driver_id}/topup", response_model=DriverTopupRead)
async def topup_driver(
    driver_id: DriverId,
    body: DriverTopupWrite,
    request: Request,
    admin: CurrentAdmin,
):
    row_id, balance = await service(request).topup_driver(
        driver_id=driver_id,
        amount=body.amount,
        admin_tg_id=admin,
        reason=body.reason,
        meta=request_meta(
            request,
            request.app.state.settings.admin_audit_ip_secret
            or request.app.state.settings.csrf_secret,
        ),
    )
    return DriverTopupRead(id=row_id, balance=balance)
