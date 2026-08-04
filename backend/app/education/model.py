"""Ta'lim domeni: guruhlar, o'quvchilar va kurs arizalari.

Uch jadval birga ko'chiriladi, chunki arizani qabul qilish amali
uchalasini bitta tranzaksiyada o'zgartiradi: guruh tekshiriladi,
o'quvchi yoziladi, ariza holati yangilanadi.

`id` qiymatlari eski JSON yozuvlaridan **o'zgarmasdan** ko'chiriladi.
Shu sababli `group_id` va `course_item_id` kabi havolalar qayta
xaritalashsiz ishlaydi. Ular tashqi kalit qilinmagan: eski ma'lumotda
mavjud bo'lmagan guruhga ishora qiluvchi o'quvchilar uchraydi va ular
migratsiyada yo'qolmasligi kerak.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
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
    joined_date: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=""
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
