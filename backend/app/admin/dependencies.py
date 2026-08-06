"""Har bir admin endpointi o'z HttpOnly admin sessiyasini tekshiradi."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.admin.service import AdminAuthService
from app.core.errors import ApiError


def admin_auth_service(request: Request) -> AdminAuthService:
    return request.app.state.admin_auth_service


async def require_admin(request: Request) -> int:
    """Admin Telegram ID sini qaytaradi, aks holda 401."""
    service: AdminAuthService = request.app.state.admin_auth_service
    token = request.cookies.get(
        request.app.state.settings.admin_cookie_name, ""
    )
    telegram_user_id = await service.resolve(token)
    if telegram_user_id is None:
        raise ApiError(
            401,
            "admin_session_required",
            "Admin sessiyasi topilmadi yoki tugagan.",
        )
    return telegram_user_id


CurrentAdmin = Annotated[int, Depends(require_admin)]
AdminServiceDep = Annotated[AdminAuthService, Depends(admin_auth_service)]
