"""Ovqatlanish xizmati — mavzu bo'yicha mixin'lar.

`DiningService` 1 290 qatorlik bitta faylda edi: stollar, zakazlar,
oshxona, kassa va muammolar aralash.

    base     -> bog'liqliklar, huquq, bildirishnomalar
    places   -> stollar va bron
    orders   -> ichki zakazlar
    kitchen  -> oshxona
    cashier  -> kassa (to'lov, ombor, chek)
    problems -> muammoli zakazlar
"""

from app.dining.service_parts.service import DiningService

__all__ = ["DiningService"]
