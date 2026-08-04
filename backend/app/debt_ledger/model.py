from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Debtor(Base):
    __tablename__ = "debtors"
    __table_args__ = (
        CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_debtors_name_required",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default=""
    )
    note: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    due: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default=""
    )
    created_by_staff_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("staff_members.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class DebtTransaction(Base):
    __tablename__ = "debt_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('debt','payment')",
            name="ck_debt_transactions_type",
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_debt_transactions_amount_positive",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    debtor_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("debtors.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    transaction_type: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("orders.id", ondelete="SET NULL"),
    )
    cash_receipt_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("cash_receipts.id", ondelete="CASCADE"),
    )
    performed_by_staff_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("staff_members.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


Index(
    "ix_debtors_business_created",
    Debtor.business_account_id,
    Debtor.created_at.desc(),
    Debtor.id.desc(),
)
Index(
    "uq_debtors_business_legacy",
    Debtor.business_account_id,
    Debtor.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "ix_debt_transactions_debtor_date",
    DebtTransaction.business_account_id,
    DebtTransaction.debtor_id,
    DebtTransaction.transaction_date,
    DebtTransaction.id,
)
Index(
    "ix_debt_transactions_receipt",
    DebtTransaction.business_account_id,
    DebtTransaction.cash_receipt_id,
)
Index(
    "uq_debt_transactions_business_legacy",
    DebtTransaction.business_account_id,
    DebtTransaction.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "uq_debt_transactions_order_debt",
    DebtTransaction.order_id,
    unique=True,
    postgresql_where=text(
        "order_id IS NOT NULL AND transaction_type = 'debt'"
    ),
    sqlite_where=text(
        "order_id IS NOT NULL AND transaction_type = 'debt'"
    ),
)
