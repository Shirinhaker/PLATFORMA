"""Eski nom — `app.dining.service_parts` paketiga qayta-eksport.

Fayl 1 290 qator edi. Endi har bir bo'lim o'z mixin'ida
(`service_parts/__init__.py` da xarita bor).
"""

from app.dining.service_parts import DiningService
from app.dining.service_parts.helpers import *  # noqa: F403

__all__ = ["DiningService"]
