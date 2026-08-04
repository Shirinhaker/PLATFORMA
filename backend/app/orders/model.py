from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


ORDER_STATUSES = (
    "new", "accepted", "rejected", "preparing", "tayyor", "cancelled",
    "courier_assigned", "courier_arrived_store", "handoff_waiting_seller",
    "in_delivery", "courier_arrived_customer", "pickup_waiting_customer",
    "delivered_waiting_customer", "done",
)
PAYMENT_STATUSES = (
    "", "pending", "submitted", "recheck", "disputed", "confirmed", "rejected"
)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "customer_kind IN ('user', 'business')",
            name="ck_orders_customer_kind",
        ),
        CheckConstraint(
            "provider_kind IN ('user', 'business')",
            name="ck_orders_provider_kind",
        ),
        CheckConstraint(
            "order_type IN ('delivery', 'pickup', 'booking')",
            name="ck_orders_order_type",
        ),
        CheckConstraint(
            "order_category IN ('product', 'service')",
            name="ck_orders_order_category",
        ),
        CheckConstraint(
            "status IN ('new', 'accepted', 'rejected', 'preparing', 'tayyor', "
            "'cancelled', 'courier_assigned', 'courier_arrived_store', "
            "'handoff_waiting_seller', 'in_delivery', "
            "'courier_arrived_customer', 'pickup_waiting_customer', "
            "'delivered_waiting_customer', 'done')",
            name="ck_orders_status",
        ),
        CheckConstraint(
            "payment_status IN ('', 'pending', 'submitted', 'recheck', "
            "'disputed', 'confirmed', 'rejected')",
            name="ck_orders_payment_status",
        ),
        CheckConstraint("total_amount >= 0", name="ck_orders_total_amount"),
        CheckConstraint("qty > 0", name="ck_orders_qty"),
        CheckConstraint(
            "delivery_lat IS NULL OR delivery_lat BETWEEN -90 AND 90",
            name="ck_orders_delivery_lat",
        ),
        CheckConstraint(
            "delivery_lng IS NULL OR delivery_lng BETWEEN -180 AND 180",
            name="ck_orders_delivery_lng",
        ),
        CheckConstraint(
            "problem_solution IN ('', 'pickup', 'wait', 'new_receipt')",
            name="ck_orders_problem_solution",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    customer_account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    customer_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    customer_phone: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    provider_account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    provider_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    provider_phone: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    item_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("catalog_items.id", ondelete="SET NULL")
    )
    listing_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("listings.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    note: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    order_category: Mapped[str] = mapped_column(String(20), nullable=False, default="product")
    address: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    desired_time: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    delivery_lat: Mapped[float | None] = mapped_column(Float)
    delivery_lng: Mapped[float | None] = mapped_column(Float)
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=1)
    total_amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    pay_type: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    debtor_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("debtors.id", ondelete="SET NULL")
    )
    receipt_message_id: Mapped[int | None] = mapped_column(BigInteger)
    problem_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    problem_reason: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    problem_note: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    problem_solution: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    problem_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    problem_resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_event: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    customer_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handed_off_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seller_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    customer_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_order_items_qty"),
        CheckConstraint("line_total >= 0", name="ck_order_items_line_total"),
        CheckConstraint(
            "kind IN ('product', 'service')",
            name="ck_order_items_kind",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    catalog_item_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("catalog_items.id", ondelete="SET NULL")
    )
    item_name: Mapped[str] = mapped_column(String(180), nullable=False)
    price_text: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False, default="dona")
    line_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    note: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="product")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrderMessage(Base):
    __tablename__ = "order_messages"
    __table_args__ = (
        CheckConstraint(
            "sender_kind IN ('user', 'business')",
            name="ck_order_messages_sender_kind",
        ),
        CheckConstraint(
            "media_type IN ('text', 'photo')",
            name="ck_order_messages_media_type",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    sender_account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    sender_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    media_object_key: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    legacy_media_url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    reply_to_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("order_messages.id", ondelete="SET NULL")
    )
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index("ix_orders_customer_created", Order.customer_account_id, Order.created_at)
Index("ix_orders_provider_created", Order.provider_account_id, Order.created_at)
Index(
    "ix_orders_provider_unread", Order.provider_account_id, Order.updated_at,
    postgresql_where=text("provider_seen_at IS NULL"),
)
Index(
    "ix_orders_customer_unread", Order.customer_account_id, Order.updated_at,
    postgresql_where=text("customer_seen_at IS NULL"),
)
Index("ix_orders_item_id", Order.item_id)
Index("ix_orders_listing_id", Order.listing_id)
Index("ix_order_items_order", OrderItem.order_id, OrderItem.id)
Index("ix_order_items_catalog_item", OrderItem.catalog_item_id)
Index("ix_order_messages_order_created", OrderMessage.order_id, OrderMessage.created_at, OrderMessage.id)
Index("ix_order_messages_sender", OrderMessage.sender_account_id, OrderMessage.created_at)
Index("ix_order_messages_reply_to", OrderMessage.reply_to_id)
Index(
    "uq_order_items_legacy", OrderItem.order_id, OrderItem.legacy_source_id,
    unique=True, postgresql_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "uq_order_messages_legacy", OrderMessage.order_id, OrderMessage.legacy_source_id,
    unique=True, postgresql_where=text("legacy_source_id IS NOT NULL"),
)
