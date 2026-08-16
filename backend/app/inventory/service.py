"""Eski nom — `app.inventory.service_parts` paketiga qayta-eksport.

Fayl 1001 qator edi. Endi har bir bo'lim o'z mixin'ida
(`service_parts/__init__.py` da xarita bor).
"""

from app.inventory.service_parts import InventoryService
from app.inventory.service_parts.helpers import *  # noqa: F403

# `import *` maxfiy nomlarni olmaydi, lekin ba'zilariga jonli
# kod tayanadi (masalan `auth/shared_login.py`). `__all__` ga ham
# yoziladi, aks holda linter ularni "ishlatilmagan" deb o'chiradi.
from app.inventory.service_parts.helpers import (
    _money_per_unit,
    _money_total,
    _number,
    _quantity,
)

__all__ = [
    "InventoryService",
    "_money_per_unit",
    "_money_total",
    "_number",
    "_quantity",
]
