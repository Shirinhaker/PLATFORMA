"""Admin kirishi: kod yuborish, tasdiqlash, chiqish."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.admin.dependencies import AdminServiceDep, CurrentAdmin
from app.admin.schemas import (
    AdminAuthStart,
    AdminAuthStarted,
    AdminAuthVerify,
    AdminIdentity,
)

router = APIRouter()


@router.post("/auth/start", response_model=AdminAuthStarted)
async def admin_auth_start(
    body: AdminAuthStart,
    service: AdminServiceDep,
) -> AdminAuthStarted:
    """Ro'yxatdagi Telegram ID ga bir martalik kod yuboradi."""
    result = await service.start(telegram_user_id=body.telegram_user_id)
    return AdminAuthStarted(**result)


@router.post("/auth/verify", response_model=AdminIdentity)
async def admin_auth_verify(
    body: AdminAuthVerify,
    request: Request,
    response: Response,
    service: AdminServiceDep,
) -> AdminIdentity:
    token = await service.verify(challenge_id=body.challenge_id, code=body.code)
    settings = request.app.state.settings
    response.set_cookie(
        settings.admin_cookie_name,
        token,
        max_age=settings.admin_session_ttl_seconds,
        httponly=True,
        secure=settings.environment in {"staging", "production"},
        samesite="lax",
        path="/",
    )
    telegram_user_id = await service.resolve(token)
    return AdminIdentity(telegram_user_id=telegram_user_id or 0)


@router.get("/auth/me", response_model=AdminIdentity)
async def admin_auth_me(admin: CurrentAdmin) -> AdminIdentity:
    return AdminIdentity(telegram_user_id=admin)


@router.post("/auth/logout", status_code=204)
async def admin_auth_logout(
    request: Request,
    response: Response,
    service: AdminServiceDep,
) -> Response:
    settings = request.app.state.settings
    await service.logout(request.cookies.get(settings.admin_cookie_name, ""))
    response.delete_cookie(settings.admin_cookie_name, path="/")
    return Response(status_code=204)
