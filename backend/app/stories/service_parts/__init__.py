"""Storieslarni joylash va ko'rish.

`StoryService` ilgari 521 qatorlik bitta faylda edi.
Endi har bir mavzu o'z mixin'ida:

    base            -> story javobi, media manzili
    publishing      -> joylash, o'chirish, shikoyat
    reading         -> lenta, ko'rish, ko'ruvchilar

Klass nomi va metod nomlari o'zgarmadi.
"""

from app.stories.service_parts.service import StoryService

__all__ = ["StoryService"]
