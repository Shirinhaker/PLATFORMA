"""Admin moderatsiyasi: akkaunt, cheklov, kontent.

`AdminModerationService` ilgari 566 qatorlik bitta faylda edi.
Endi har bir mavzu o'z mixin'ida:

    base            -> akkauntni topish, faol cheklovlar
    accounts        -> akkauntlar ro'yxati va kartochkasi
    restrictions    -> cheklov qo'yish va olib tashlash
    content         -> kontent holati

Klass nomi va metod nomlari o'zgarmadi.
"""

from app.admin.moderation.service import AdminModerationService

__all__ = ["AdminModerationService"]
