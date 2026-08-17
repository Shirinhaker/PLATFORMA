"""Navbat jadvallariga barcha so'rovlar.

`QueueRepository` ilgari 619 qatorlik bitta faylda edi.
Endi har bir mavzu o'z mixin'ida:

    base         -> biznes/foydalanuvchi/xizmat izlash, javob shakli
    providers    -> provayderlar va bog'lanishlar
    entries      -> navbat yozuvlari va raqam berish
    listing      -> ro'yxatlar

Klass nomi va metod nomlari o'zgarmadi.
"""

from app.queues.repository_parts.helpers import (
    ACTIVE_STATUSES,
    active_provider_count,
    active_queue_count,
)
from app.queues.repository_parts.repository import QueueRepository

__all__ = [
    "ACTIVE_STATUSES",
    "QueueRepository",
    "active_provider_count",
    "active_queue_count",
]
