"""Moderatsiya, shikoyatlar va audit tarixi jadvallari.

v1656 `moderation.py` va `admin_audit.py` bilan bir xil tuzilma.

Audit jurnali **faqat qo'shiladi**: uni o'zgartirish yoki o'chirish
baza darajasida to'siladi. v1656 da bu SQLite triggerlari bilan
qilingan, PostgreSQL da esa `plpgsql` funksiyasi bilan.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    JSON,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


ACTOR_TYPES = ("user", "business")
RESTRICTIONS = ("content_hidden", "account_blocked")
CONTENT_STATUSES = ("hidden", "visible", "removed")
CONTENT_KINDS = (
    "product", "service", "advertisement", "business", "profile",
    "listing", "story",
)
REPORT_REASONS = ("fraud", "spam", "illegal", "abuse", "other")
REPORT_STATUSES = ("open", "reviewing", "resolved", "dismissed")


class AccountRestriction(Base):
    """Akkaunt cheklovi.

    `content_hidden` egasining kabinetidagi ma'lumotni o'chirmaydi —
    faqat public qidiruv, xarita va takliflardan yashiradi.
    """

    __tablename__ = "account_restrictions"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('user', 'business')",
            name="ck_account_restrictions_actor",
        ),
        CheckConstraint(
            "restriction IN ('content_hidden', 'account_blocked')",
            name="ck_account_restrictions_kind",
        ),
        CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_account_restrictions_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restriction: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="active"
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_by_tg_id: Mapped[int | None] = mapped_column(BigInteger)
    revoked_reason: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class AdminAccountNote(Base):
    """Adminning ichki izohi — egasiga ko'rinmaydi."""

    __tablename__ = "admin_account_notes"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('user', 'business')",
            name="ck_admin_account_notes_actor",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    admin_tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ContentModeration(Base):
    """Kontent ko'rinishi tarixi — oxirgi yozuv joriy holat."""

    __tablename__ = "content_moderation"
    __table_args__ = (
        CheckConstraint(
            "status IN ('hidden', 'visible', 'removed')",
            name="ck_content_moderation_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    content_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    content_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by_tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ModerationReport(Base):
    __tablename__ = "moderation_reports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'reviewing', 'resolved', 'dismissed')",
            name="ck_moderation_reports_status",
        ),
        CheckConstraint(
            "reason_code IN ('fraud', 'spam', 'illegal', 'abuse', 'other')",
            name="ck_moderation_reports_reason",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    reporter_account_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    content_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    content_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(16), nullable=False)
    comment: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="open"
    )
    assigned_admin_tg_id: Mapped[int | None] = mapped_column(BigInteger)
    resolution: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AdminAuditLog(Base):
    """Har bir admin amali. Yozilgandan keyin o'zgarmaydi."""

    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    admin_tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=""
    )
    before_state: Mapped[dict[str, Any]] = mapped_column(
        "before_json", JSON, nullable=False, default=dict
    )
    after_state: Mapped[dict[str, Any]] = mapped_column(
        "after_json", JSON, nullable=False, default=dict
    )
    reason: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    # Xom IP hech qachon saqlanmaydi, faqat HMAC xeshi.
    ip_hash: Mapped[str] = mapped_column(
        String(128), nullable=False, server_default=""
    )
    user_agent: Mapped[str] = mapped_column(
        String(500), nullable=False, server_default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


# Bir akkauntda bir turdagi faol cheklov bittadan ortiq bo'lmaydi.
Index(
    "uq_account_restriction_active",
    AccountRestriction.actor_type,
    AccountRestriction.actor_id,
    AccountRestriction.restriction,
    unique=True,
    postgresql_where=text("status = 'active'"),
    sqlite_where=text("status = 'active'"),
)
Index(
    "ix_account_restrictions_lookup",
    AccountRestriction.actor_type,
    AccountRestriction.actor_id,
    AccountRestriction.status,
)
Index(
    "ix_admin_account_notes_actor",
    AdminAccountNote.actor_type,
    AdminAccountNote.actor_id,
    AdminAccountNote.id.desc(),
)
Index(
    "ix_content_moderation_latest",
    ContentModeration.content_kind,
    ContentModeration.content_id,
    ContentModeration.id.desc(),
)
Index(
    "ix_moderation_reports_queue",
    ModerationReport.status,
    ModerationReport.created_at,
    ModerationReport.id,
)
Index(
    "ix_moderation_reports_content",
    ModerationReport.content_kind,
    ModerationReport.content_id,
)
Index(
    "ix_admin_audit_action_created",
    AdminAuditLog.action,
    AdminAuditLog.created_at.desc(),
    AdminAuditLog.id.desc(),
)
Index(
    "ix_admin_audit_admin_created",
    AdminAuditLog.admin_tg_id,
    AdminAuditLog.created_at.desc(),
    AdminAuditLog.id.desc(),
)
