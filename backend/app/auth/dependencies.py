from dataclasses import dataclass
from datetime import UTC, datetime
import hmac
from typing import Annotated

from fastapi import Depends, Header, Request

from app.accounts.model import AccountType
from app.auth.security import derive_csrf
from app.core.errors import ApiError


@dataclass(frozen=True)
class CurrentAccount:
    account_id: int
    account_type: AccountType
    session_token: str


async def require_current_account(request: Request) -> CurrentAccount:
    session_token = request.cookies.get(
        request.app.state.settings.auth_cookie_name
    )
    if not session_token:
        raise ApiError(
            401,
            "authentication_required",
            "Avval tizimga kiring.",
        )
    identity = await request.app.state.auth_service.resolve_session(
        session_token,
        datetime.now(UTC),
    )
    if identity is None:
        raise ApiError(
            401,
            "session_expired",
            "Sessiya tugagan. Qayta kiring.",
        )
    request.state.session_identity = identity
    return CurrentAccount(
        account_id=identity.account_id,
        account_type=identity.account_type,
        session_token=session_token,
    )


async def require_csrf(
    current: Annotated[CurrentAccount, Depends(require_current_account)],
    request: Request,
    x_csrf_token: str = Header(
        default="",
        alias="X-CSRF-Token",
    ),
) -> CurrentAccount:
    expected = derive_csrf(
        current.session_token,
        request.app.state.settings.csrf_secret,
    )
    if not hmac.compare_digest(expected, x_csrf_token):
        raise ApiError(
            403,
            "csrf_failed",
            "So‘rov xavfsizlik tekshiruvidan o‘tmadi.",
        )
    return current
