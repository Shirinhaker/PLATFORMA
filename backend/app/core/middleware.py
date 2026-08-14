from contextvars import ContextVar
import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.cache.rate_limit import consume_rate_limit


logger = logging.getLogger("koprik.http")
request_id_context: ContextVar[str] = ContextVar(
    "request_id",
    default="",
)
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")
_ADMIN_AUTH_LIMITS = {
    "/api/v1/admin/auth/start": (10, 10 * 60),
    "/api/v1/admin/auth/verify": (30, 10 * 60),
}


async def _admin_auth_ip_limit(request):
    config = _ADMIN_AUTH_LIMITS.get(request.url.path)
    if request.method != "POST" or config is None:
        return None

    wrapper = getattr(request.app.state, "redis", None)
    redis = getattr(wrapper, "client", None) if wrapper is not None else None
    if redis is None:
        settings = request.app.state.settings
        if settings.environment == "test":
            return None
        return JSONResponse(
            status_code=503,
            content={
                "code": "admin_auth_rate_limit_unavailable",
                "message": "Admin kirish himoyasi vaqtincha mavjud emas.",
                "request_id": request_id_context.get(),
            },
        )

    limit, window_seconds = config
    client_ip = request.client.host if request.client is not None else "unknown"
    try:
        result = await consume_rate_limit(
            redis,
            f"admin-auth:ip:{request.url.path.rsplit('/', 1)[-1]}:{client_ip}",
            limit,
            window_seconds,
        )
    except Exception:
        logger.exception("admin_auth_rate_limit_failed")
        return JSONResponse(
            status_code=503,
            content={
                "code": "admin_auth_rate_limit_unavailable",
                "message": "Admin kirish himoyasi vaqtincha mavjud emas.",
                "request_id": request_id_context.get(),
            },
        )
    if result.allowed:
        return None
    return JSONResponse(
        status_code=429,
        content={
            "code": "admin_auth_ip_rate_limited",
            "message": "Bu manzildan juda ko‘p admin kirish urinishlari bo‘ldi.",
            "request_id": request_id_context.get(),
        },
        headers={"Retry-After": str(result.retry_after_seconds)},
    )


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        supplied = request.headers.get("X-Request-Id", "")
        request_id = (
            supplied
            if SAFE_REQUEST_ID.fullmatch(supplied)
            else str(uuid.uuid4())
        )
        token = request_id_context.set(request_id)
        started = time.perf_counter()
        try:
            limited = await _admin_auth_ip_limit(request)
            if limited is not None:
                response = limited
            else:
                response = await call_next(request)
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            response.headers["X-Request-Id"] = request_id
            response.headers["Server-Timing"] = f"app;dur={duration_ms:.2f}"
            logger.info(
                "request method=%s path=%s status=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "request_failed method=%s path=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                duration_ms,
            )
            raise
        finally:
            request_id_context.reset(token)
