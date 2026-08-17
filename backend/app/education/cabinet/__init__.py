"""O'quv kabinetidagi guruh va o'quvchi amallari.

`EducationCabinetService` ilgari 605 qatorlik bitta faylda edi.
Endi har bir mavzu o'z mixin'ida:

    base            -> bog'liqliklar
    groups          -> guruhlar
    students        -> o'quvchilar va guruh tarixi

Klass nomi va metod nomlari o'zgarmadi.
"""

from app.education.cabinet.service import EducationCabinetService

__all__ = ["EducationCabinetService"]
