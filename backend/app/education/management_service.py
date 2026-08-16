"""Eski nom — `app.education.management` paketiga qayta-eksport.

Fayl 1 562 qator edi: guruhlar, o'quvchilar, davomat, to'lovlar,
o'qituvchilar va oylik bir joyda. Endi har biri o'z mixin'ida
(`management/__init__.py` da xarita bor).

Bu qobiq ataylab qoldirildi — `router.py` va testlar shu nomdan import
qiladi. Yangi kod `app.education.management` dan olsin.
"""

from app.education.management import EducationManagementService
from app.education.management.helpers import *  # noqa: F403

__all__ = ["EducationManagementService"]
