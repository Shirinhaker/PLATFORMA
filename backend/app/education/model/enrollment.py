"""Kursga yozilish va davomat jadvallari."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


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
    phone: Mapped[str] = mapped_column(String(40), nullable=False, server_default="")
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
