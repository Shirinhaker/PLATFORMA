"""Eski nom — `app.queues.service_parts` paketiga qayta-eksport.

Fayl 1 173 qator edi. Endi har bir bo'lim o'z mixin'ida
(`service_parts/__init__.py` da xarita bor).
"""

from app.queues.service_parts import QueueService
from app.queues.service_parts.helpers import *  # noqa: F403

__all__ = ["QueueService"]
