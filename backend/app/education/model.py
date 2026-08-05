"""Ta'lim domeni: o'quv jarayoni, to'lovlar va kurs arizalari.

K7 guruh, o'quvchi va arizani ko'chirgan. K9 statistika uchun kerak
bo'ladigan davomat, o'quvchi to'lovi, o'qituvchi va maosh to'lovini
shu domenning relatsion qismiga qo'shadi.

Eski JSON identifikatorlari `legacy_source_id` maydonlarida saqlanadi.
Bizneslar kesishib ketmasligi uchun barcha bog'lanishlar backfillda
`business_account_id` bilan birga xaritalanadi.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


ENROLLMENT_STATUSES = ("new", "accepted", "rejected")
# Ariza shu holatlarda bo'lsa, o'sha kursga qayta yozilib bo'lmaydi.
ACTIVE_ENROLLMENT_SQL = "status IN ('new', 'accepted')"


class EducationGroup(Base):
    __tablename__ = "education_groups"
    __table_args__ = (
        CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_education_groups_name_required",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    course_item_id: Mapped[int | None] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    teacher_id: Mapped[int | None] = mapped_column(BigInteger)
    legacy_teacher_id: Mapped[int | None] = mapped_column(BigInteger)
    teacher_name: Mapped[str] = mapped_column(
        String(160), nullable=False, server_default=""
    )
    room_name: Mapped[str] = mapped_column(
        String(80), nullable=False, server_default=""
    )
    capacity: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    weekdays: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=""
    )
    lesson_from: Mapped[str] = mapped_column(
        String(5), nullable=False, server_default=""
    )
    lesson_to: Mapped[str] = mapped_column(
        String(5), nullable=False, server_default=""
    )
    start_date: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=""
    )
    end_date: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=""
    )
    billing_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="monthly"
    )
    package_lessons: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    package_price: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class EducationStudent(Base):
    __tablename__ = "education_students"
    __table_args__ = (
        CheckConstraint(
            "monthly_fee >= 0",
            name="ck_education_students_monthly_fee",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    group_id: Mapped[int | None] = mapped_column(BigInteger)
    user_account_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
    )
    legacy_user_id: Mapped[int | None] = mapped_column(BigInteger)
    full_name: Mapped[str] = mapped_column(
        String(160), nullable=False, server_default=""
    )
    phone: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default=""
    )
    parent_name: Mapped[str] = mapped_column(
        String(160), nullable=False, server_default=""
    )
    parent_phone: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default=""
    )
    birth_date: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=""
    )
    joined_date: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=""
    )
    payment_start_date: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=""
    )
    lesson_package_override: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    monthly_fee: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'accepted', 'rejected')",
            name="ck_course_enrollments_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    legacy_business_id: Mapped[int | None] = mapped_column(BigInteger)
    course_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_account_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
    )
    legacy_user_id: Mapped[int | None] = mapped_column(BigInteger)
    customer_name: Mapped[str] = mapped_column(
        String(160), nullable=False, server_default=""
    )
    phone: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default=""
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="new"
    )
    group_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class EducationAttendance(Base):
    __tablename__ = "education_attendance"
    __table_args__ = (
        CheckConstraint(
            "attendance_status IN ('present', 'late', 'excused', 'absent')",
            name="ck_education_attendance_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    group_id: Mapped[int | None] = mapped_column(BigInteger)
    student_id: Mapped[int | None] = mapped_column(BigInteger)
    legacy_group_id: Mapped[int | None] = mapped_column(BigInteger)
    legacy_student_id: Mapped[int | None] = mapped_column(BigInteger)
    lesson_date: Mapped[str] = mapped_column(String(10), nullable=False)
    attendance_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="present"
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class EducationPayment(Base):
    __tablename__ = "education_payments"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_education_payments_amount"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    student_id: Mapped[int | None] = mapped_column(BigInteger)
    legacy_student_id: Mapped[int | None] = mapped_column(BigInteger)
    payment_month: Mapped[str] = mapped_column(
        String(7), nullable=False, server_default=""
    )
    amount: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    pay_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="naqd"
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    legacy_sale_id: Mapped[int | None] = mapped_column(BigInteger)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    legacy_voided_by: Mapped[int | None] = mapped_column(BigInteger)
    void_reason: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class EducationTeacher(Base):
    __tablename__ = "education_teachers"
    __table_args__ = (
        CheckConstraint(
            "salary_type IN ('monthly', 'per_lesson')",
            name="ck_education_teachers_salary_type",
        ),
        CheckConstraint(
            "salary_amount >= 0",
            name="ck_education_teachers_salary_amount",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    full_name: Mapped[str] = mapped_column(
        String(160), nullable=False, server_default=""
    )
    phone: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default=""
    )
    specialty: Mapped[str] = mapped_column(
        String(160), nullable=False, server_default=""
    )
    hired_date: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=""
    )
    salary_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="monthly"
    )
    salary_amount: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class EducationTeacherPayment(Base):
    __tablename__ = "education_teacher_payments"
    __table_args__ = (
        CheckConstraint(
            "amount >= 0", name="ck_education_teacher_payments_amount"
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    teacher_id: Mapped[int | None] = mapped_column(BigInteger)
    legacy_teacher_id: Mapped[int | None] = mapped_column(BigInteger)
    payment_month: Mapped[str] = mapped_column(
        String(7), nullable=False, server_default=""
    )
    amount: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    pay_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="naqd"
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    expense_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("expenses.id", ondelete="SET NULL"),
    )
    legacy_expense_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


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
# Takroriy arizani baza to'sadi — avval buning uchun butun ro'yxat
# Pythonda skanerlanardi.
Index(
    "uq_course_enrollments_active_account",
    CourseEnrollment.business_account_id,
    CourseEnrollment.course_item_id,
    CourseEnrollment.user_account_id,
    unique=True,
    postgresql_where=text(
        f"user_account_id IS NOT NULL AND {ACTIVE_ENROLLMENT_SQL}"
    ),
    sqlite_where=text(
        f"user_account_id IS NOT NULL AND {ACTIVE_ENROLLMENT_SQL}"
    ),
)
Index(
    "uq_course_enrollments_active_legacy_user",
    CourseEnrollment.business_account_id,
    CourseEnrollment.course_item_id,
    CourseEnrollment.legacy_user_id,
    unique=True,
    postgresql_where=text(
        f"legacy_user_id IS NOT NULL AND {ACTIVE_ENROLLMENT_SQL}"
    ),
    sqlite_where=text(
        f"legacy_user_id IS NOT NULL AND {ACTIVE_ENROLLMENT_SQL}"
    ),
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
