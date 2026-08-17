"""Bildirishnomalar, sozlamalar va push qurilmalari.

`NotificationService` ilgari 544 qatorlik bitta faylda edi.
Endi har bir mavzu o'z mixin'ida:

    base            -> ko'rinish, o'qilganlik, filtr
    inbox           -> kiruvchi quti
    preferences     -> sozlama va filtrlar
    devices         -> push qurilmalari
    events          -> hodisadan kelib chiqadigan xabarlar

Klass nomi va metod nomlari o'zgarmadi.
"""

from app.notifications.service_parts.helpers import (
    price_number,
)
from app.notifications.service_parts.service import NotificationService

__all__ = [
    "NotificationService",
    "price_number",
]
