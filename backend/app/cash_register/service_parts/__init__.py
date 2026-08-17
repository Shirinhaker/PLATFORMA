"""Kassa cheklari va buyurtma to'lovlari.

`CashRegisterService` ilgari 676 qatorlik bitta faylda edi.
Endi har bir mavzu o'z mixin'ida:

    base            -> kun chegarasi, kassa huquqi, chek shakli
    receipts        -> cheklar: katalog, ro'yxat, yaratish, o'chirish
    orders          -> buyurtma to'lovi va savdo yozuvi

Klass nomi va metod nomlari o'zgarmadi.
"""

from app.cash_register.service_parts.service import CashRegisterService

__all__ = ["CashRegisterService"]
