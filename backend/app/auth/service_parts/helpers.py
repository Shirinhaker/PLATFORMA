"""Autentifikatsiya uchun konstantalar."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError

SessionFactory = Callable[
    [],
    AbstractAsyncContextManager[AsyncSession],
]


logger = logging.getLogger(__name__)


_CACHE_MISS = object()


_SESSION_CACHE_PREFIX = "auth:session:v1:"


_SESSION_REVOKED_PREFIX = "auth:session:revoked:v1:"


_SESSION_TOUCH_INTERVAL = timedelta(minutes=5)


_CACHE_SESSION_SCRIPT = """
if redis.call('EXISTS', KEYS[2]) == 1 then
  return 0
end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
return 1
"""


_REVOKE_CACHED_SESSION_SCRIPT = """
redis.call('SET', KEYS[1], '1', 'EX', ARGV[1])
redis.call('DEL', KEYS[2])
return 1
"""


INVALID_CREDENTIALS = ApiError(
    401,
    "invalid_credentials",
    "Login yoki parol noto‘g‘ri.",
)


INVALID_CODE = ApiError(
    400,
    "invalid_code",
    "Tasdiqlash kodi noto‘g‘ri yoki muddati tugagan.",
)
