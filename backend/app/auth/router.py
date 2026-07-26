from datetime import UTC, datetime
import hmac
from typing import Any

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from app.auth.dependencies import (
    CurrentAccount,
    require_csrf,
    require_current_account,
)
from app.auth.schemas import RegistrationStart
from app.auth.security import sha256_token
from app.cache.rate_limit import consume_rate_limit
from app.core.errors import ApiError


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
RATE_LIMIT_MESSAGE = (
    "Juda ko‘p urinish. Birozdan keyin qayta urinib ko‘ring."
)


class LoginStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class ChallengeVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: int = Field(gt=0)
    code: str = Field(pattern=r"^\d{6}$")
    device_name: str = Field(default="", max_length=200)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def _rate_limit_redis(request: Request):
    redis = request.app.state.redis
    client = getattr(redis, "client", None)
    return client if client is not None and not callable(client) else redis


async def _enforce_rate_limit(
    request: Request,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    result = await consume_rate_limit(
        _rate_limit_redis(request),
        key,
        limit,
        window_seconds,
    )
    if not result.allowed:
        raise ApiError(
            429,
            "rate_limited",
            RATE_LIMIT_MESSAGE,
            headers={
                "Retry-After": str(result.retry_after_seconds),
            },
        )


def _set_session_cookie(
    response: Response,
    request: Request,
    session_token: str,
) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=session_token,
        max_age=settings.session_ttl_seconds,
        secure=True,
        httponly=True,
        samesite="none" if settings.environment == "staging" else "lax",
        path="/",
    )


def _authenticated_payload(result, *, include_credentials: bool) -> dict:
    excluded = {"session_token"}
    if not include_credentials:
        excluded.update({"login", "password"})
    return jsonable_encoder(
        result.model_dump(exclude=excluded),
    )


@router.post("/register/start")
async def register_start(
    body: RegistrationStart,
    request: Request,
):
    await _enforce_rate_limit(
        request,
        f"auth:register:start:ip:{_client_ip(request)}",
        5,
        10 * 60,
    )
    return await request.app.state.auth_service.start_registration(
        body,
        datetime.now(UTC),
    )


@router.post("/register/verify")
async def register_verify(
    body: ChallengeVerifyRequest,
    request: Request,
    response: Response,
):
    await _enforce_rate_limit(
        request,
        f"auth:challenge:verify:ip:{_client_ip(request)}",
        10,
        5 * 60,
    )
    result = await request.app.state.auth_service.verify_registration(
        body.request_id,
        body.code,
        body.device_name,
        datetime.now(UTC),
    )
    _set_session_cookie(response, request, result.session_token)
    return _authenticated_payload(result, include_credentials=True)


@router.post("/login/start")
async def login_start(
    body: LoginStartRequest,
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
    return await request.app.state.auth_service.start_login(
        normalized_login,
        body.password,
        datetime.now(UTC),
    )


@router.post("/login/verify")
async def login_verify(
    body: ChallengeVerifyRequest,
    request: Request,
    response: Response,
):
    await _enforce_rate_limit(
        request,
        f"auth:challenge:verify:ip:{_client_ip(request)}",
        10,
        5 * 60,
    )
    result = await request.app.state.auth_service.verify_login(
        body.request_id,
        body.code,
        body.device_name,
        datetime.now(UTC),
    )
    _set_session_cookie(response, request, result.session_token)
    return _authenticated_payload(result, include_credentials=False)


@router.post("/challenges/{request_id}/resend")
async def resend_challenge(
    request_id: int,
    request: Request,
):
    await _enforce_rate_limit(
        request,
        f"auth:challenge:resend:id:{request_id}",
        1,
        60,
    )
    await _enforce_rate_limit(
        request,
        f"auth:challenge:resend:ip:{_client_ip(request)}",
        5,
        10 * 60,
    )
    return await request.app.state.auth_service.resend_challenge(
        request_id,
        datetime.now(UTC),
    )


@router.get("/session")
async def get_session(
    request: Request,
    current: CurrentAccount = Depends(require_current_account),
):
    return request.state.session_identity


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    current: CurrentAccount = Depends(require_csrf),
) -> Response:
    await request.app.state.auth_service.revoke_session(
        current.session_token,
        datetime.now(UTC),
    )
    settings = request.app.state.settings
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        secure=True,
        httponly=True,
        samesite="none" if settings.environment == "staging" else "lax",
    )
    response.status_code = 204
    return response


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_secret: str | None = Header(
        default=None,
        alias="X-Telegram-Bot-Api-Secret-Token",
    ),
) -> dict[str, bool]:
    expected = request.app.state.settings.telegram_webhook_secret
    provided = x_telegram_secret or ""
    if not expected or not hmac.compare_digest(provided, expected):
        raise ApiError(
            403,
            "telegram_webhook_forbidden",
            "Telegram webhook siri noto‘g‘ri.",
        )

    payload: dict[str, Any] = await request.json()
    message = payload.get("message")
    if not isinstance(message, dict):
        return {"ok": True}
    chat = message.get("chat")
    text = message.get("text")
    if (
        not isinstance(chat, dict)
        or chat.get("type") != "private"
        or not isinstance(chat.get("id"), int)
        or not isinstance(text, str)
        or not text.startswith("/start ")
    ):
        return {"ok": True}

    start_token = text.removeprefix("/start ").strip()
    if not start_token:
        return {"ok": True}
    await _enforce_rate_limit(
        request,
        f"auth:telegram:webhook:chat:{chat['id']}",
        60,
        60,
    )
    await request.app.state.auth_service.activate_deep_link(
        start_token,
        chat["id"],
        datetime.now(UTC),
    )
    return {"ok": True}
