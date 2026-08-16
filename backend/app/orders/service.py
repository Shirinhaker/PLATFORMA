"""Eski nom — `app.orders.service_parts` paketiga qayta-eksport.

Fayl 1 359 qator edi: yaratish, ro'yxatlar, holat, to'lov, muammolar
va yozishmalar bir klassda. Endi har biri o'z mixin'ida
(`service_parts/__init__.py` da xarita bor).

Bu qobiq ataylab qoldirildi — `main.py`, `router.py` va testlar shu
nomdan import qiladi.
"""

from app.orders.service_parts import OrderService
from app.orders.service_parts.helpers import *  # noqa: F403

__all__ = [
    "OrderService",
]
