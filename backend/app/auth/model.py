from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    JSON,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.accounts.model import ACCOUNT_TYPE_ENUM, AccountType
from app.db.base import Base


class PendingRegistration(Base):
    __tablename__ = "pending_registrations"
    __table_args__ = (
        Index("ix_pending_registrations_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    account_type: Mapped[AccountType] = mapped_column(
        ACCOUNT_TYPE_ENUM,
        nullable=False,
    )
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )


class AuthChallenge(Base):
    __tablename__ = "auth_challenges"
    __table_args__ = (
        Index("ix_auth_challenges_start_expires_at", "start_expires_at"),
        Index("ix_auth_challenges_code_expires_at", "code_expires_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    account_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
    )
    pending_registration_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("pending_registrations.id", ondelete="CASCADE"),
    )
    start_token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
    )
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger)
    code_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    code_hash: Mapped[str | None] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    start_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    code_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    code_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index(
            "ix_auth_sessions_active_account",
            "account_id",
            "expires_at",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
    )
    device_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
