"""Buyurtma xizmati — mavzu bo'yicha mixin'lar.

`OrderService` 1 359 qatorlik bitta faylda edi: yaratish, ro'yxatlar,
holat, to'lov, muammolar va yozishmalar aralash.

    base      -> bog'liqliklar, egalik, javob shakli
    creation  -> buyurtma yaratish
    listing   -> ro'yxatlar va "ko'rildi"
    status    -> holat o'zgarishi
    payment   -> to'lov
    problems  -> muammoli buyurtma
    messaging -> yozishmalar
"""

from app.orders.service_parts.service import OrderService

__all__ = ["OrderService"]
