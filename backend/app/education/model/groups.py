"""Guruh, o'quvchi va guruh tarixi jadvallari."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


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
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    weekdays: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    lesson_from: Mapped[str] = mapped_column(
        String(5), nullable=False, server_default=""
    )
    lesson_to: Mapped[str] = mapped_column(String(5), nullable=False, server_default="")
    start_date: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=""
    )
    end_date: Mapped[str] = mapped_column(String(20), nullable=False, server_default="")
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
    phone: Mapped[str] = mapped_column(String(40), nullable=False, server_default="")
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


class EducationStudentGroupHistory(Base):
    """O'quvchining guruhdan guruhga ko'chishi tarixi.

    v1656da ko'chirish avvalgi yozuvni yopib, yangisini ochadi — shu
    sababli o'quvchi qaysi oyda qaysi guruhda bo'lganini bilib bo'ladi.
    """

    __tablename__ = "education_student_group_history"

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
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    group_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    started_date: Mapped[str] = mapped_column(String(20), nullable=False)
    ended_date: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=""
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
