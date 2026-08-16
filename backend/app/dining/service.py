"""Eski nom — `app.dining.service_parts` paketiga qayta-eksport.

Fayl 1 290 qator edi. Endi har bir bo'lim o'z mixin'ida
(`service_parts/__init__.py` da xarita bor).
"""

from app.dining.service_parts import DiningService
from app.dining.service_parts.helpers import *  # noqa: F403

# `import *` maxfiy nomlarni olmaydi, lekin ba'zilariga jonli
# kod tayanadi (masalan `auth/shared_login.py`). `__all__` ga ham
# yoziladi, aks holda linter ularni "ishlatilmagan" deb o'chiradi.
from app.dining.service_parts.helpers import (
    _line_total,
    _price_of,
    _quantity,
    _unix,
)

__all__ = [
    "DiningService",
    "_line_total",
    "_price_of",
    "_quantity",
    "_unix",
]
