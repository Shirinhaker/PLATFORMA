"""O'quv markazi boshqaruvi uchun barcha so'rovlar.

`EducationManagementRepository` ilgari 546 qatorlik bitta faylda edi.
Endi har bir mavzu o'z mixin'ida:

    base         -> biznes profilini topish
    groups       -> guruhlar va o'quvchilar
    attendance   -> davomat
    payments     -> o'quvchi to'lovlari
    teachers     -> o'qituvchilar
    payroll      -> oylik
    cash         -> kassa cheki

Klass nomi va metod nomlari o'zgarmadi.
"""

from app.education.management_repository_parts.repository import (
    EducationManagementRepository,
)

__all__ = ["EducationManagementRepository"]
