"""To'lovlar domeni: narx katalogi, so'rov, chek va audit izi.

v1656dagi beshta jadval saqlanadi: narxlar, to'lov usullari, to'lov
so'rovlari, chek urinishlari va holat o'zgarishlari jurnali.

Chek fayli endi R2'da saqlanadi (`receipt_object_key`) — v1656da u
serverning lokal diskida turardi va bir nechta nusxa ishlaganda
topilmasdi.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


SERVICE_TYPES = ("advertisement", "subscription", "listing")
REQUEST_STATUSES = ("pending", "approved", "rejected", "cancelled")
ATTEMPT_STATUSES = ("pending", "approved", "rejected", "superseded")


class PlatformPrice(Base):
    __tablename__ = "platform_prices"
    __table_args__ = (
        CheckConstraint("amount_uzs >= 0", name="ck_platform_prices_amount"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    price_code: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    amount_uzs: Mapped[int] = mapped_column(BigInteger, nullable=False)
    service_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=""
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    active: Mapped[bool] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    method_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    recipient_name: Mapped[str] = mapped_column(
        String(160), nullable=False, server_default=""
    )
    instructions: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    active: Mapped[bool] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class PaymentRequest(Base):
    __tablename__ = "payment_requests"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('user', 'business')",
            name="ck_payment_requests_actor_type",
        ),
        CheckConstraint(
            "service_type IN ('advertisement', 'subscription', 'listing')",
            name="ck_payment_requests_service_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_payment_requests_status",
        ),
        CheckConstraint(
            "amount_snapshot >= 0", name="ck_payment_requests_amount"
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    request_code: Mapped[str] = mapped_column(
        String(40), nullable=False, unique=True
    )
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    service_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[int | None] = mapped_column(BigInteger)
    plan_code: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=""
    )
    duration_months: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    unit_price_snapshot: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    amount_snapshot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default="UZS"
    )
    price_code: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=""
    )
    target_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    payment_method_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("payment_methods.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="pending"
    )
    reviewed_by_account_id: Mapped[int | None] = mapped_column(BigInteger)
    approved_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    rejected_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    cancelled_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    public_reason: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    internal_note: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"
    __table_args__ = (
        CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected', 'superseded')",
            name="ck_payment_attempts_review_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    payment_request_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("payment_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    receipt_object_key: Mapped[str] = mapped_column(
        String(1024), nullable=False
    )
    receipt_filename: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=""
    )
    receipt_mime: Mapped[str] = mapped_column(String(120), nullable=False)
    receipt_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    submitted_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reviewed_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    review_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="pending"
    )
    review_reason: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    payment_request_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("payment_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str] = mapped_column(String(16), nullable=False)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=""
    )
    reason: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


Index(
    "ix_payment_requests_owner",
    PaymentRequest.account_id,
    PaymentRequest.actor_type,
    PaymentRequest.created_at.desc(),
)
Index(
    "ix_payment_requests_status",
    PaymentRequest.status,
    PaymentRequest.created_at,
    PaymentRequest.id,
)
Index(
    "uq_payment_requests_legacy",
    PaymentRequest.legacy_source_id,
    unique=True,
    postgresql_where=PaymentRequest.legacy_source_id.is_not(None),
    sqlite_where=PaymentRequest.legacy_source_id.is_not(None),
)
Index(
    "uq_payment_attempts_no",
    PaymentAttempt.payment_request_id,
    PaymentAttempt.attempt_no,
    unique=True,
)
Index(
    "ix_payment_attempts_receipt_hash",
    PaymentAttempt.receipt_sha256,
)
Index(
    "ix_payment_events_request",
    PaymentEvent.payment_request_id,
    PaymentEvent.id,
)


class BusinessSubscription(Base):
    """Faol obuna. Tasdiqlangan to'lov shu yerga yoziladi."""

    __tablename__ = "business_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "plan_code IN ('plus', 'pro')",
            name="ck_business_subscriptions_plan",
        ),
        CheckConstraint(
            "status IN ('active', 'superseded', 'expired')",
            name="ck_business_subscriptions_status",
        ),
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
    plan_code: Mapped[str] = mapped_column(String(16), nullable=False)
    duration_months: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="active"
    )
    is_demo: Mapped[bool] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    payment_request_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("payment_requests.id", ondelete="SET NULL"),
    )
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


Index(
    "ix_business_subscriptions_active",
    BusinessSubscription.business_account_id,
    BusinessSubscription.status,
    BusinessSubscription.expires_at,
)
# Bir to'lov faqat bir marta obunaga aylanadi.
Index(
    "uq_business_subscriptions_payment",
    BusinessSubscription.payment_request_id,
    unique=True,
    postgresql_where=BusinessSubscription.payment_request_id.is_not(None),
    sqlite_where=BusinessSubscription.payment_request_id.is_not(None),
)
