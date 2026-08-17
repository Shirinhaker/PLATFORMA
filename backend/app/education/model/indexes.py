"""Jadval indekslari.

Bular modul darajasida e'lon qilingan `Index(...)` chaqiruvlari —
ular SQLAlchemy metadata'siga yozilishi uchun modellardan **keyin**
bajarilishi shart. Shuning uchun alohida modulda va `__init__` da
eng oxirida import qilinadi.

Diqqat: bulardan biri takroriy yozilishni to'sadigan UNIQUE indeks.
Ular tushib qolsa, cheklov jimgina yo'qoladi.
"""

from __future__ import annotations

from sqlalchemy import Index, text

from app.education.model.constants import ACTIVE_ENROLLMENT_SQL
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

Index(
    "ix_education_groups_business",
    EducationGroup.business_account_id,
    EducationGroup.status,
    EducationGroup.id,
)
Index(
    "uq_education_groups_legacy",
    EducationGroup.business_account_id,
    EducationGroup.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "ix_education_students_business",
    EducationStudent.business_account_id,
    EducationStudent.status,
    EducationStudent.id,
)
Index(
    "ix_education_students_group",
    EducationStudent.business_account_id,
    EducationStudent.group_id,
)
Index(
    "uq_education_students_legacy",
    EducationStudent.business_account_id,
    EducationStudent.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "ix_course_enrollments_business",
    CourseEnrollment.business_account_id,
    CourseEnrollment.status,
    CourseEnrollment.id,
)
Index(
    "uq_course_enrollments_legacy",
    CourseEnrollment.business_account_id,
    CourseEnrollment.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "uq_course_enrollments_active_account",
    CourseEnrollment.business_account_id,
    CourseEnrollment.course_item_id,
    CourseEnrollment.user_account_id,
    unique=True,
    postgresql_where=text(f"user_account_id IS NOT NULL AND {ACTIVE_ENROLLMENT_SQL}"),
    sqlite_where=text(f"user_account_id IS NOT NULL AND {ACTIVE_ENROLLMENT_SQL}"),
)
Index(
    "uq_course_enrollments_active_legacy_user",
    CourseEnrollment.business_account_id,
    CourseEnrollment.course_item_id,
    CourseEnrollment.legacy_user_id,
    unique=True,
    postgresql_where=text(f"legacy_user_id IS NOT NULL AND {ACTIVE_ENROLLMENT_SQL}"),
    sqlite_where=text(f"legacy_user_id IS NOT NULL AND {ACTIVE_ENROLLMENT_SQL}"),
)
Index(
    "ix_education_attendance_business_date",
    EducationAttendance.business_account_id,
    EducationAttendance.lesson_date,
    EducationAttendance.group_id,
)
Index(
    "ix_education_attendance_student_date",
    EducationAttendance.business_account_id,
    EducationAttendance.student_id,
    EducationAttendance.lesson_date,
)
Index(
    "uq_education_attendance_legacy",
    EducationAttendance.business_account_id,
    EducationAttendance.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "uq_education_attendance_day",
    EducationAttendance.business_account_id,
    EducationAttendance.group_id,
    EducationAttendance.student_id,
    EducationAttendance.lesson_date,
    unique=True,
    postgresql_where=text("group_id IS NOT NULL AND student_id IS NOT NULL"),
    sqlite_where=text("group_id IS NOT NULL AND student_id IS NOT NULL"),
)
Index(
    "ix_education_payments_business_created",
    EducationPayment.business_account_id,
    EducationPayment.created_at,
    EducationPayment.id,
)
Index(
    "ix_education_payments_student_month",
    EducationPayment.business_account_id,
    EducationPayment.student_id,
    EducationPayment.payment_month,
    EducationPayment.id,
)
Index(
    "uq_education_payments_legacy",
    EducationPayment.business_account_id,
    EducationPayment.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "uq_education_payments_cash_receipt",
    EducationPayment.cash_receipt_id,
    unique=True,
    postgresql_where=text("cash_receipt_id IS NOT NULL"),
    sqlite_where=text("cash_receipt_id IS NOT NULL"),
)
Index(
    "ix_education_teachers_business",
    EducationTeacher.business_account_id,
    EducationTeacher.status,
    EducationTeacher.id,
)
Index(
    "uq_education_teachers_legacy",
    EducationTeacher.business_account_id,
    EducationTeacher.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "ix_education_teacher_payments_business_created",
    EducationTeacherPayment.business_account_id,
    EducationTeacherPayment.created_at,
    EducationTeacherPayment.id,
)
Index(
    "ix_education_teacher_payments_teacher_month",
    EducationTeacherPayment.business_account_id,
    EducationTeacherPayment.teacher_id,
    EducationTeacherPayment.payment_month,
    EducationTeacherPayment.id,
)
Index(
    "uq_education_teacher_payments_legacy",
    EducationTeacherPayment.business_account_id,
    EducationTeacherPayment.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "ix_education_student_group_history_student",
    EducationStudentGroupHistory.business_account_id,
    EducationStudentGroupHistory.student_id,
    EducationStudentGroupHistory.started_date,
    EducationStudentGroupHistory.id,
)
Index(
    "uq_education_student_group_history_legacy",
    EducationStudentGroupHistory.business_account_id,
    EducationStudentGroupHistory.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
