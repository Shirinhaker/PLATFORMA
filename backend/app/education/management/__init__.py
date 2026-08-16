"""O'quv markazi boshqaruvi.

`EducationManagementService` 1 562 qatorlik bitta faylda edi — guruhlar,
o'quvchilar, davomat, to'lovlar, o'qituvchilar va oylik hammasi aralash.

Endi har bir mavzu o'z mixin'ida. Klass nomi va metod nomlari
o'zgarmadi, ya'ni `router.py` va testlar o'sha-o'sha ishlaydi.

    base     -> bog'liqliklar va huquq tekshiruvlari
    groups   -> o'quv guruhlari
    students -> o'quvchilar va kartochka
    attendance -> davomat
    payments -> to'lovlar
    teachers -> o'qituvchilar
    payroll  -> oylik
    helpers  -> sana/oy hisoblari, konstantalar
"""

from app.education.management.service import EducationManagementService

__all__ = ["EducationManagementService"]
