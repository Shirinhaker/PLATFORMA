"""Eski nom — `app.auth.service_parts` paketiga qayta-eksport.

Fayl 865 qator edi. Endi har bir bo'lim o'z mixin'ida
(`service_parts/__init__.py` da xarita bor).
"""

from app.auth.service_parts import AuthService
from app.auth.service_parts.helpers import *  # noqa: F403

# `import *` maxfiy nomlarni olmaydi, lekin ba'zilariga jonli
# kod tayanadi (masalan `auth/shared_login.py`). `__all__` ga ham
# yoziladi, aks holda linter ularni "ishlatilmagan" deb o'chiradi.
from app.auth.service_parts.helpers import (
    _CACHE_MISS,
    _CACHE_SESSION_SCRIPT,
    _REVOKE_CACHED_SESSION_SCRIPT,
    _SESSION_CACHE_PREFIX,
    _SESSION_REVOKED_PREFIX,
    _SESSION_TOUCH_INTERVAL,
)

__all__ = [
    "_CACHE_MISS",
    "_CACHE_SESSION_SCRIPT",
    "_REVOKE_CACHED_SESSION_SCRIPT",
    "_SESSION_CACHE_PREFIX",
    "_SESSION_REVOKED_PREFIX",
    "_SESSION_TOUCH_INTERVAL",
    "AuthService",
]
