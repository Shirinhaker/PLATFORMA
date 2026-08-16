"""Navbat xizmati — mavzu bo'yicha mixin'lar.

`QueueService` 1 173 qatorlik bitta faylda edi.

    base         -> bog'liqliklar, kontekst, javob shakli
    providers    -> shifokor/xizmat va ish jadvali
    availability -> bo'sh vaqtlar
    booking      -> navbatga yozilish
    listing      -> ro'yxatlar
    lifecycle    -> bekor qilish, holat, almashtirish
"""

from app.queues.service_parts.service import QueueService

__all__ = ["QueueService"]
