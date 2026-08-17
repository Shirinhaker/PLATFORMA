"""Xodimlar, huquqlar, davomat va seanslar.

`StaffService` ilgari 646 qatorlik bitta faylda edi.
Endi har bir mavzu o'z mixin'ida:

    base            -> biznes profili, egalik, xodim javobi
    members         -> xodim qo'shish, tahrirlash, holat
    access          -> huquqlar, jadval, kasblar
    attendance      -> davomat
    sessions        -> xodim kirishi va seansi

Klass nomi va metod nomlari o'zgarmadi.
"""

from app.staff.service_parts.helpers import (
    UZBEKISTAN_TZ,
)
from app.staff.service_parts.service import StaffService

__all__ = [
    "UZBEKISTAN_TZ",
    "StaffService",
]
