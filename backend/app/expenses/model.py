from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
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


class ExpenseCategory(Base):
    __tablename__ = "expense_categories"
    __table_args__ = (
        CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_expense_categories_name_required",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        CheckConstraint(
            "length(trim(category)) > 0",
            name="ck_expenses_category_required",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="manual"
    )
    inventory_stock_move_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("inventory_stock_moves.id", ondelete="CASCADE"),
    )
    performed_by_staff_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("staff_members.id", ondelete="SET NULL"),
    )
    actor_name_snapshot: Mapped[str] = mapped_column(
        String(160), nullable=False, server_default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


Index(
    "ix_expenses_business_created",
    Expense.business_account_id,
    Expense.created_at.desc(),
    Expense.id.desc(),
)
Index(
    "uq_expenses_business_legacy",
    Expense.business_account_id,
    Expense.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "uq_expenses_stock_move",
    Expense.inventory_stock_move_id,
    unique=True,
    postgresql_where=text("inventory_stock_move_id IS NOT NULL"),
    sqlite_where=text("inventory_stock_move_id IS NOT NULL"),
)
Index(
    "ix_expense_categories_business",
    ExpenseCategory.business_account_id,
    ExpenseCategory.created_at,
    ExpenseCategory.id,
)
Index(
    "uq_expense_categories_business_legacy",
    ExpenseCategory.business_account_id,
    ExpenseCategory.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "uq_expense_categories_business_name",
    ExpenseCategory.business_account_id,
    ExpenseCategory.name,
    unique=True,
)
