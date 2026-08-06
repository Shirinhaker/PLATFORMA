"""Admin paneli: alohida challenge va sessiya jadvallari.

v1656 (`admin_auth.py`) bilan bir xil: admin sessiyasi oddiy foydalanuvchi
sessiyasidan **butunlay ajratilgan**. Bu ataylab shunday — o'g'irlangan
foydalanuvchi sessiyasi admin huquqini bermaydi.

Bazada raw token saqlanmaydi, faqat SHA-256 xeshi: baza sizib chiqqanda
cookie qiymati tiklanmaydi.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Identity,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminAuthChallenge(Base):
    """Adminga yuborilgan bir martalik kod."""

    __tablename__ = "admin_auth_challenges"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


Index(
    "ix_admin_auth_challenges_owner",
    AdminAuthChallenge.telegram_user_id,
    AdminAuthChallenge.created_at.desc(),
)
Index(
    "ix_admin_sessions_active",
    AdminSession.telegram_user_id,
    AdminSession.expires_at,
    postgresql_where=text("revoked_at IS NULL"),
    sqlite_where=text("revoked_at IS NULL"),
)
