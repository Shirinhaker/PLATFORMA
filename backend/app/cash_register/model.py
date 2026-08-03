from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CashReceiptCounter(Base):
    __tablename__ = "cash_receipt_counters"
    __table_args__ = (
        CheckConstraint(
            "last_receipt_no >= 0",
            name="ck_cash_receipt_counters_non_negative",
        ),
    )

    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    last_receipt_no: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class CashReceipt(Base):
    __tablename__ = "cash_receipts"
    __table_args__ = (
        CheckConstraint(
            "source IN ('manual','order','dining','education','debt_payment')",
            name="ck_cash_receipts_source",
        ),
        CheckConstraint(
            "pay_type IN ('','naqd','karta','qarz')",
            name="ck_cash_receipts_pay_type",
        ),
        CheckConstraint(
            "receipt_no IS NULL OR receipt_no > 0",
            name="ck_cash_receipts_receipt_no_positive",
        ),
        UniqueConstraint(
            "business_account_id",
            "receipt_no",
            name="uq_cash_receipts_business_number",
        ),
        UniqueConstraint("order_id", name="uq_cash_receipts_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    receipt_no: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="manual"
    )
    order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("orders.id", ondelete="RESTRICT"),
    )
    legacy_order_source_id: Mapped[int | None] = mapped_column(BigInteger)
    legacy_group_key: Mapped[str | None] = mapped_column(String(160))
    pay_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=""
    )
    debtor_name_snapshot: Mapped[str] = mapped_column(
        String(160), nullable=False, server_default=""
    )
    legacy_debtor_source_id: Mapped[int | None] = mapped_column(BigInteger)
    note: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    created_by_staff_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("staff_members.id", ondelete="SET NULL"),
    )
    actor_name_snapshot: Mapped[str] = mapped_column(
        String(160), nullable=False, server_default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class CashReceiptLine(Base):
    __tablename__ = "cash_receipt_lines"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_cash_receipt_lines_qty"),
        CheckConstraint("unit_price >= 0", name="ck_cash_receipt_lines_price"),
        CheckConstraint("total > 0", name="ck_cash_receipt_lines_total"),
        CheckConstraint("cost_total >= 0", name="ck_cash_receipt_lines_cost"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    receipt_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("cash_receipts.id", ondelete="CASCADE"),
        nullable=False,
    )
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    catalog_item_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("catalog_items.id", ondelete="SET NULL"),
    )
    inventory_item_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("inventory_items.id", ondelete="SET NULL"),
    )
    legacy_source_key: Mapped[str | None] = mapped_column(String(160))
    item_name: Mapped[str] = mapped_column(String(220), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    unit: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default="dona"
    )
    unit_price: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    total: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    cost_total: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


Index(
    "ix_cash_receipts_business_created",
    CashReceipt.business_account_id,
    CashReceipt.created_at.desc(),
    CashReceipt.id.desc(),
)
Index(
    "ix_cash_receipts_business_source",
    CashReceipt.business_account_id,
    CashReceipt.source,
    CashReceipt.created_at.desc(),
)
Index(
    "uq_cash_receipts_legacy_group",
    CashReceipt.business_account_id,
    CashReceipt.legacy_group_key,
    unique=True,
    postgresql_where=text("legacy_group_key IS NOT NULL"),
    sqlite_where=text("legacy_group_key IS NOT NULL"),
)
Index("ix_cash_receipt_lines_receipt", CashReceiptLine.receipt_id, CashReceiptLine.id)
Index(
    "ix_cash_receipt_lines_catalog",
    CashReceiptLine.business_account_id,
    CashReceiptLine.catalog_item_id,
)
Index(
    "uq_cash_receipt_lines_legacy_source",
    CashReceiptLine.business_account_id,
    CashReceiptLine.legacy_source_key,
    unique=True,
    postgresql_where=text("legacy_source_key IS NOT NULL"),
    sqlite_where=text("legacy_source_key IS NOT NULL"),
)
