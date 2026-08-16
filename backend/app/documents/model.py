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


class DocumentCounterparty(Base):
    __tablename__ = "document_counterparties"
    __table_args__ = (
        CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_document_counterparties_name_required",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    ctype: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    director: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    address: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    inn: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    account: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    bank: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    mfo: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    note: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class BusinessDocument(Base):
    __tablename__ = "business_documents"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('ichki', 'kiruvchi', 'chiquvchi')",
            name="ck_business_documents_direction",
        ),
        CheckConstraint(
            "status IN ('', 'yuborilgan', 'kutilmoqda', 'qabul qilindi', 'rad etildi')",
            name="ck_business_documents_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    number: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    doc_date: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    contractor_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("document_counterparties.id", ondelete="SET NULL"),
    )
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sender_business_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
    )
    sender_name_snapshot: Mapped[str] = mapped_column(
        String(120), nullable=False, default=""
    )
    receiver_tax_id: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="")
    source_document_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("business_documents.id", ondelete="SET NULL"),
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


Index(
    "ix_document_counterparties_business_name",
    DocumentCounterparty.business_account_id,
    DocumentCounterparty.name,
    DocumentCounterparty.id,
)
Index(
    "uq_document_counterparties_business_legacy",
    DocumentCounterparty.business_account_id,
    DocumentCounterparty.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "ix_business_documents_business_direction",
    BusinessDocument.business_account_id,
    BusinessDocument.direction,
    BusinessDocument.id.desc(),
)
Index(
    "uq_business_documents_business_legacy",
    BusinessDocument.business_account_id,
    BusinessDocument.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "ix_business_documents_source",
    BusinessDocument.source_document_id,
)
