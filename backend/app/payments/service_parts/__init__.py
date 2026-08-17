"""Tarif, obuna va to'lov arizalari.

`PaymentService` ilgari 688 qatorlik bitta faylda edi.
Endi har bir mavzu o'z mixin'ida:

    base            -> egalik, urinishlar tarixi, hodisa yozuvi
    catalog         -> tarif katalogi va joriy obuna
    requests        -> ariza yuborish va qayta yuborish
    review          -> ko'rik va obunani faollashtirish

Klass nomi va metod nomlari o'zgarmadi.
"""

from app.payments.service_parts.service import PaymentService

__all__ = ["PaymentService"]
