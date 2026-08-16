"""Ombor xizmati — mavzu bo'yicha mixin'lar.

base       -> FIFO yechish/qaytarish, huquq
cash_lines -> kassa savdosi bilan bog'liq yechish
items      -> mahsulotlar
moves      -> kirim/chiqim harakatlari
production -> retsept va ishlab chiqarish
"""

from app.inventory.service_parts.service import InventoryService

__all__ = ["InventoryService"]
