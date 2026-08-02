from __future__ import annotations

from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    JSON,
    String,
    Text,
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
