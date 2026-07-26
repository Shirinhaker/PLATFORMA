from contextvars import ContextVar
import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware


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
