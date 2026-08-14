from contextvars import ContextVar
import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware


logger = logging.getLogger("koprik.http")
request_id_context: ContextVar[str] = ContextVar(
    "request_id",
    default="",
)
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


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
