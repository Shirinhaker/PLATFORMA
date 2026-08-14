from contextvars import ContextVar
import re
import uuid
import time

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.metrics import HTTP_LATENCY, HTTP_REQUESTS


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
        try:
            response = await call_next(request)
        finally:
            request_id_context.reset(token)
        response.headers["X-Request-Id"] = request_id
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = getattr(request.scope.get("route"), "path", request.url.path)
            HTTP_REQUESTS.labels(request.method, route, str(status)).inc()
            HTTP_LATENCY.labels(request.method, route).observe(
                time.perf_counter() - started
            )
