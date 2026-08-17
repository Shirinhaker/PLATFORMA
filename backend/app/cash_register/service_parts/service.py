"""`CashRegisterService` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.cash_register.service_parts.base import CashRegisterServiceBase
from app.cash_register.service_parts.orders import OrdersMixin
from app.cash_register.service_parts.receipts import ReceiptsMixin


class CashRegisterService(
    ReceiptsMixin,
    OrdersMixin,
    CashRegisterServiceBase,
):
    """Kassa cheklari va buyurtma to'lovlari."""
