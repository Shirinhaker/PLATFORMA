"""Eski nom — `app.taxi.service_parts` paketiga qayta-eksport.

Fayl 793 qator edi. Endi har bir bo'lim o'z mixin'ida
(`service_parts/__init__.py` da xarita bor).
"""

from app.taxi.service_parts import TaxiService
from app.taxi.service_parts.helpers import *  # noqa: F403

__all__ = [
    "TaxiService",
]
