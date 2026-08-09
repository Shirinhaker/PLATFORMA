from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class MessageConversation(Base):
    __tablename__ = "message_conversations"
    __table_args__ = (
        CheckConstraint(
            "low_account_id < high_account_id",
            name="ck_message_conversations_canonical_pair",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    low_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    high_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class MessageConversationMember(Base):
    __tablename__ = "message_conversation_members"

    conversation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("message_conversations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "sender_account_id <> receiver_account_id",
            name="ck_messages_distinct_participants",
        ),
        CheckConstraint(
            "media_type IN ('text', 'photo')",
            name="ck_messages_media_type",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    conversation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("message_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    receiver_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="text"
    )
    media_object_key: Mapped[str] = mapped_column(
        String(1024), nullable=False, default=""
    )
    legacy_media_url: Mapped[str] = mapped_column(
        String(2048), nullable=False, default=""
    )
    file_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default=""
    )
    reply_to_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("messages.id", ondelete="SET NULL"),
    )
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


Index(
    "uq_message_conversations_pair",
    MessageConversation.low_account_id,
    MessageConversation.high_account_id,
    unique=True,
)
Index(
    "ix_message_conversations_low_updated",
    MessageConversation.low_account_id,
    MessageConversation.updated_at,
)
Index(
    "ix_message_conversations_high_updated",
    MessageConversation.high_account_id,
    MessageConversation.updated_at,
)
Index(
    "ix_message_members_account_conversation",
    MessageConversationMember.account_id,
    MessageConversationMember.conversation_id,
)
Index(
    "ix_message_conversation_member",
    Message.conversation_id,
    Message.created_at,
    Message.id,
)
Index("ix_messages_sender", Message.sender_account_id, Message.created_at)
Index("ix_messages_receiver", Message.receiver_account_id, Message.created_at)
Index("ix_messages_reply_to", Message.reply_to_id)
Index(
    "ix_messages_receiver_unread",
    Message.receiver_account_id,
    Message.conversation_id,
    Message.created_at,
    postgresql_where=text("read_at IS NULL"),
)
Index(
    "uq_messages_legacy_source",
    Message.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
)
