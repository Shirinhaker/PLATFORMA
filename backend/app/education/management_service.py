"""Eski nom — `app.education.management` paketiga qayta-eksport.

Fayl 1 562 qator edi: guruhlar, o'quvchilar, davomat, to'lovlar,
o'qituvchilar va oylik bir joyda. Endi har biri o'z mixin'ida
(`management/__init__.py` da xarita bor).

Bu qobiq ataylab qoldirildi — `router.py` va testlar shu nomdan import
qiladi. Yangi kod `app.education.management` dan olsin.
"""

from app.education.management import EducationManagementService
from app.education.management.helpers import *  # noqa: F403

# `import *` maxfiy nomlarni olmaydi, lekin ba'zilariga jonli
# kod tayanadi (masalan `auth/shared_login.py`). `__all__` ga ham
# yoziladi, aks holda linter ularni "ishlatilmagan" deb o'chiradi.
from app.education.management.helpers import (
    _add_month,
    _billing_status,
    _date,
    _month,
    _payment_local_date,
    _student_start,
    _teacher_read,
)

__all__ = [
    "EducationManagementService",
    "_add_month",
    "_billing_status",
    "_date",
    "_month",
    "_payment_local_date",
    "_student_start",
    "_teacher_read",
]
