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


class AIChatMessage(Base):
    __tablename__ = "ai_chat_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="ck_ai_chat_messages_role"),
        CheckConstraint("length(trim(text)) > 0", name="ck_ai_chat_messages_text"),
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
    role: Mapped[str] = mapped_column(String(12), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="local")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index(
    "ix_ai_chat_messages_business_created",
    AIChatMessage.business_account_id,
    AIChatMessage.created_at,
    AIChatMessage.id,
)
Index(
    "uq_ai_chat_messages_business_legacy",
    AIChatMessage.business_account_id,
    AIChatMessage.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
