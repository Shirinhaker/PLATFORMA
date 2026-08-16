from __future__ import annotations

from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('user', 'business')",
            name="ck_notifications_account_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_type: Mapped[str] = mapped_column(String(16), nullable=False)
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("orders.id", ondelete="SET NULL"),
    )
    listing_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("listings.id", ondelete="SET NULL"),
    )
    dining_order_id: Mapped[int | None] = mapped_column(BigInteger)
    medical_queue_id: Mapped[int | None] = mapped_column(BigInteger)
    ride_id: Mapped[int | None] = mapped_column(BigInteger)
    target_staff_id: Mapped[int | None] = mapped_column(BigInteger)
    target_permission: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="",
    )
    action_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="",
    )
    requires_action: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    read_at: Mapped[int | None] = mapped_column(BigInteger)
    resolved_at: Mapped[int | None] = mapped_column(BigInteger)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )


Index(
    "uq_notifications_owner_event",
    Notification.account_id,
    Notification.account_type,
    Notification.event_key,
    unique=True,
)
Index(
    "ix_notifications_owner_actionable",
    Notification.account_id,
    Notification.account_type,
    Notification.created_at,
    postgresql_where=text(
        "requires_action = true AND is_read = false AND resolved_at IS NULL"
    ),
    sqlite_where=text(
        "requires_action = 1 AND is_read = 0 AND resolved_at IS NULL"
    ),
)
Index(
    "ix_notifications_owner_listing",
    Notification.account_id,
    Notification.account_type,
    Notification.listing_id,
    postgresql_where=text("listing_id IS NOT NULL"),
    sqlite_where=text("listing_id IS NOT NULL"),
)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('user', 'business')",
            name="ck_notification_preferences_account_type",
        ),
    )

    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    account_type: Mapped[str] = mapped_column(
        String(16),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    orders_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class NotificationFilter(Base):
    __tablename__ = "notification_filters"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('user', 'business')",
            name="ck_notification_filters_account_type",
        ),
        CheckConstraint(
            "category IN ('uy', 'ish', 'moshina', 'hayvon', 'texnika', 'boshqa')",
            name="ck_notification_filters_category",
        ),
        CheckConstraint(
            "price_min >= 0 AND price_max >= 0",
            name="ck_notification_filters_prices",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_type: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    region: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    district: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    price_min: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    price_max: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    keyword: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


Index(
    "ix_notification_filters_match",
    NotificationFilter.category,
    NotificationFilter.account_id,
)
Index(
    "ix_notification_filters_owner",
    NotificationFilter.account_id,
    NotificationFilter.account_type,
    NotificationFilter.id,
)
Index(
    "uq_notification_filters_legacy_source",
    NotificationFilter.account_id,
    NotificationFilter.account_type,
    NotificationFilter.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)


class PushDevice(Base):
    __tablename__ = "push_devices"
    __table_args__ = (
        CheckConstraint(
            "platform IN ('android', 'ios', 'web')",
            name="ck_push_devices_platform",
        ),
        UniqueConstraint("token", name="uq_push_devices_token"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    token: Mapped[str] = mapped_column(String(4096), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    device_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    app_version: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_seen_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


Index("ix_push_devices_owner_enabled", PushDevice.account_id, PushDevice.enabled)


class PushOutbox(Base):
    __tablename__ = "push_outbox"
    __table_args__ = (
        UniqueConstraint(
            "notification_id",
            "device_id",
            name="uq_push_outbox_notification_device",
        ),
        CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed')",
            name="ck_push_outbox_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    notification_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
    )
    device_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("push_devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    available_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_attempt_at: Mapped[int | None] = mapped_column(BigInteger)
    sent_at: Mapped[int | None] = mapped_column(BigInteger)


Index("ix_push_outbox_status_available", PushOutbox.status, PushOutbox.available_at)
Index(
    "ix_notifications_owner_created",
    Notification.account_id,
    Notification.account_type,
    Notification.created_at,
    Notification.id,
)
Index(
    "ix_notifications_owner_unread",
    Notification.account_id,
    Notification.account_type,
    Notification.created_at,
    postgresql_where=text("is_read = false"),
    sqlite_where=text("is_read = 0"),
)
Index(
    "ix_notifications_owner_order",
    Notification.account_id,
    Notification.account_type,
    Notification.order_id,
    postgresql_where=text("order_id IS NOT NULL"),
    sqlite_where=text("order_id IS NOT NULL"),
)
