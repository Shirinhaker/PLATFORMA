from datetime import UTC, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.accounts.model import AccountType
from app.auth.router import _client_ip, _enforce_rate_limit
from app.auth.security import sha256_token


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class SharedLoginStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)
    cabinet_type: AccountType | None = None


@router.post("/login/start")
async def shared_login_start(
    body: SharedLoginStartRequest,
    request: Request,
):
    normalized_login = body.login.strip().lower()
    await _enforce_rate_limit(
        request,
        f"auth:login:start:ip:{_client_ip(request)}",
        5,
        10 * 60,
    )
    await _enforce_rate_limit(
        request,
        f"auth:login:start:login:{sha256_token(normalized_login)}",
        5,
        10 * 60,
    )
    service = request.app.state.auth_service
    if body.cabinet_type is None:
        return await service.start_login(
            normalized_login,
            body.password,
            datetime.now(UTC),
        )
    return await service.start_login(
        normalized_login,
        body.password,
        datetime.now(UTC),
        account_type=body.cabinet_type,
    )
