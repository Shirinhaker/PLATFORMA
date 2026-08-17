"""Bildirishnomalar, sozlamalar va push qurilmalari uchun so'rovlar.

`NotificationRepository` ilgari 655 qatorlik bitta faylda edi.
Endi har bir mavzu o'z mixin'ida:

    base         -> jadval mavjudligi, push navbatiga yozish
    inbox        -> kiruvchi quti
    preferences  -> sozlama va filtrlar
    devices      -> push qurilmalari

Klass nomi va metod nomlari o'zgarmadi.
"""

from app.notifications.repository_parts.repository import NotificationRepository

__all__ = ["NotificationRepository"]
