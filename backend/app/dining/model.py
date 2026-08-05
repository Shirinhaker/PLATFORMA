"""Ovqatlanish domeni: stollar, ichki zakazlar va zakaz qatorlari.

v1656dagi uchta jadval saqlanadi (`database.py:1569-1612`): `dining_places`,
`dining_bookings` va `dining_booking_items`. Nomi `dining_orders` ga
o'zgartirildi — v1656da bitta jadval ham stol bandligini, ham zakazni
saqlagani chalkashlik tug'dirardi; `kind` ustuni ikkalasini ajratib turadi.

Vaqt ustunlari `DateTime(timezone=True)` — chunki bu domen to'lov paytida
Kassa va Ombor bilan bitta tranzaksiyada yozadi, ular esa shu turdan
foydalanadi. API javoblarida vaqt v1656dagidek unix songa aylantiriladi.
"""

from __future__ import annotations

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
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


PLACE_KINDS = ("table", "room")
ORDER_KINDS = ("order", "booking")
KITCHEN_STATUSES = ("new", "preparing", "done")
PAYMENT_STATUSES = ("open", "confirmed")
ORDER_STATUSES = ("active", "done", "cancelled")
PAY_TYPES = ("", "naqd", "karta", "qarz")


class DiningPlace(Base):
    """Zal rejasidagi stol yoki xona."""

    __tablename__ = "dining_places"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('table', 'room')",
            name="ck_dining_places_kind",
        ),
        CheckConstraint("seats >= 0", name="ck_dining_places_seats"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    seats: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    # Zal rejasidagi koordinatalar — v1656da ham suzuvchi son.
    x: Mapped[float] = mapped_column(Float, nullable=False, server_default="4")
    y: Mapped[float] = mapped_column(Float, nullable=False, server_default="4")
    locked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class DiningOrder(Base):
    """Ichki zakaz (`kind='order'`) yoki stol bandligi (`kind='booking'`)."""

    __tablename__ = "dining_orders"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('order', 'booking')",
            name="ck_dining_orders_kind",
        ),
        CheckConstraint(
            "kitchen_status IN ('new', 'preparing', 'done')",
            name="ck_dining_orders_kitchen_status",
        ),
        CheckConstraint(
            "payment_status IN ('open', 'confirmed')",
            name="ck_dining_orders_payment_status",
        ),
        CheckConstraint(
            "status IN ('active', 'done', 'cancelled')",
            name="ck_dining_orders_status",
        ),
        CheckConstraint(
            "pay_type IN ('', 'naqd', 'karta', 'qarz')",
            name="ck_dining_orders_pay_type",
        ),
        CheckConstraint("total >= 0", name="ck_dining_orders_total"),
        CheckConstraint("guests >= 0", name="ck_dining_orders_guests"),
        # Qarzga yozilgan hisobda qarzdor bo'lishi shart.
        CheckConstraint(
            "pay_type <> 'qarz' OR debtor_id IS NOT NULL",
            name="ck_dining_orders_debt_has_debtor",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    place_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("dining_places.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)

    customer_name: Mapped[str] = mapped_column(
        String(80), nullable=False, server_default=""
    )
    phone: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=""
    )
    booking_date: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=""
    )
    booking_time: Mapped[str] = mapped_column(
        String(5), nullable=False, server_default=""
    )
    guests: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    note: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    total: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )

    waiter_staff_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("staff_members.id", ondelete="SET NULL"),
    )
    waiter_name: Mapped[str] = mapped_column(
        String(80), nullable=False, server_default=""
    )

    problem_open: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0"
    )
    problem_reason: Mapped[str] = mapped_column(
        String(80), nullable=False, server_default=""
    )
    problem_note: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    problem_opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    kitchen_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="new"
    )
    payment_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="open"
    )
    pay_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=""
    )
    debtor_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("debtors.id", ondelete="SET NULL"),
    )
    cash_receipt_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("cash_receipts.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class DiningOrderItem(Base):
    """Zakaz qatori — narx zakaz paytidagi holicha saqlanadi."""

    __tablename__ = "dining_order_items"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_dining_order_items_qty"),
        CheckConstraint("price >= 0", name="ck_dining_order_items_price"),
        CheckConstraint("total >= 0", name="ck_dining_order_items_total"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("dining_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    catalog_item_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("catalog_items.id", ondelete="SET NULL"),
    )
    name: Mapped[str] = mapped_column(String(220), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    unit: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default="dona"
    )
    price: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    total: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


Index(
    "ix_dining_places_business",
    DiningPlace.business_account_id,
    DiningPlace.id,
)
Index(
    "uq_dining_places_legacy",
    DiningPlace.business_account_id,
    DiningPlace.legacy_source_id,
    unique=True,
    postgresql_where=DiningPlace.legacy_source_id.is_not(None),
    sqlite_where=DiningPlace.legacy_source_id.is_not(None),
)
# Ofitsiant zal rejasini ochganda va kassir ochiq hisoblarni
# ko'rganda ishlatiladigan asosiy yo'l.
Index(
    "ix_dining_orders_place",
    DiningOrder.business_account_id,
    DiningOrder.place_id,
    DiningOrder.status,
    DiningOrder.id,
)
# Oshpaz ekrani: tayyorlanayotgan zakazlar.
Index(
    "ix_dining_orders_kitchen",
    DiningOrder.business_account_id,
    DiningOrder.kitchen_status,
    DiningOrder.id,
)
# Kassa "Ochiq / Muammoli / Yakunlangan" bo'limlari.
Index(
    "ix_dining_orders_cashier",
    DiningOrder.business_account_id,
    DiningOrder.payment_status,
    DiningOrder.problem_open,
    DiningOrder.id,
)
Index(
    "uq_dining_orders_legacy",
    DiningOrder.business_account_id,
    DiningOrder.legacy_source_id,
    unique=True,
    postgresql_where=DiningOrder.legacy_source_id.is_not(None),
    sqlite_where=DiningOrder.legacy_source_id.is_not(None),
)
# Bir zakaz faqat bitta chek yaratadi — ikki marta to'lov yozilmaydi.
Index(
    "uq_dining_orders_cash_receipt",
    DiningOrder.cash_receipt_id,
    unique=True,
    postgresql_where=DiningOrder.cash_receipt_id.is_not(None),
    sqlite_where=DiningOrder.cash_receipt_id.is_not(None),
)
Index(
    "ix_dining_order_items_order",
    DiningOrderItem.order_id,
    DiningOrderItem.id,
)
