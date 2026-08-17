"""O'quv markazi jadvallari.

Ilgari bitta 562 qatorlik `model.py` edi. Endi mavzu bo'yicha:

    groups      -> guruh, o'quvchi, guruh tarixi
    enrollment  -> kursga yozilish, davomat
    teachers    -> o'qituvchilar
    payments    -> o'quvchi to'lovi, o'qituvchi oyligi
    indexes     -> jadval indekslari (modellardan keyin bajariladi)

Bu `__init__` — paketning ommaviy yuzasi. `from app.education.model
import X` chaqiruvlari o'zgarmadi, va SQLAlchemy `Base.metadata` si
to'liq bo'lishi ta'minlanadi.
"""

# Indekslar eng oxirida: ular yuqoridagi modellarga tayanadi.
from app.education.model import indexes as _indexes  # noqa: F401
from app.education.model.enrollment import CourseEnrollment, EducationAttendance
from app.education.model.groups import (
    EducationGroup,
    EducationStudent,
    EducationStudentGroupHistory,
)
from app.education.model.payments import (
    EducationPayment,
    EducationTeacherPayment,
)
from app.education.model.teachers import EducationTeacher

__all__ = [
    "CourseEnrollment",
    "EducationAttendance",
    "EducationGroup",
    "EducationPayment",
    "EducationStudent",
    "EducationStudentGroupHistory",
    "EducationTeacher",
    "EducationTeacherPayment",
]
