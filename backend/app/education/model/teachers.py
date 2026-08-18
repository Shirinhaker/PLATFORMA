"""O'qituvchilar jadvali."""

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
    phone: Mapped[str] = mapped_column(String(40), nullable=False, server_default="")
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
