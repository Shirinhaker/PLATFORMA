"""Kabinet resurslari bo'yicha barcha amallar.

`BusinessOnlineService` ilgari 834 qatorlik bitta faylda edi.
Endi har bir mavzu o'z mixin'ida:

    base            -> bog'liqliklar, resurs o'qish, kesh
    crud            -> yozuvlarni o'qish/yaratish/tahrirlash/o'chirish
    actions         -> resurs amallari dispetcheri
    education       -> ta'lim resurslarini relatsion yozish
    notifications   -> amallardan keyingi bildirishnomalar

Klass nomi va metod nomlari o'zgarmadi.
"""

from app.business_online.service_parts.helpers import (
    RELATIONAL_EDUCATION_RESOURCES,
)
from app.business_online.service_parts.service import BusinessOnlineService

__all__ = [
    "RELATIONAL_EDUCATION_RESOURCES",
    "BusinessOnlineService",
]
