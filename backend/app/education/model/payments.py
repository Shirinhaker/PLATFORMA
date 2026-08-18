"""O'quvchi to'lovi va o'qituvchi oyligi jadvallari."""

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
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    pay_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="naqd"
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    legacy_sale_id: Mapped[int | None] = mapped_column(BigInteger)
    cash_receipt_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("cash_receipts.id", ondelete="SET NULL"),
    )
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    legacy_voided_by: Mapped[int | None] = mapped_column(BigInteger)
    void_reason: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class EducationTeacherPayment(Base):
    __tablename__ = "education_teacher_payments"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_education_teacher_payments_amount"),
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
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
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
