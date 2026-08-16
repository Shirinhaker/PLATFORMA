"""Eski nom — `app.queues.service_parts` paketiga qayta-eksport.

Fayl 1 173 qator edi. Endi har bir bo'lim o'z mixin'ida
(`service_parts/__init__.py` da xarita bor).
"""

from app.queues.service_parts import QueueService
from app.queues.service_parts.helpers import *  # noqa: F403

# `import *` maxfiy nomlarni olmaydi, lekin ba'zilariga jonli
# kod tayanadi (masalan `auth/shared_login.py`). `__all__` ga ham
# yoziladi, aks holda linter ularni "ishlatilmagan" deb o'chiradi.
from app.queues.service_parts.helpers import (
    _clock,
    _clock_text,
    _generated_slots,
    _medical_code,
    _slot_minutes,
)

__all__ = [
    "QueueService",
    "_clock",
    "_clock_text",
    "_generated_slots",
    "_medical_code",
    "_slot_minutes",
]
