from datetime import datetime

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
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.orders.model import Order  # noqa: F401 - registers the referenced table

DRIVER_SERVICES = ("taxi", "dostavka", "both")
RIDE_KINDS = ("taxi", "dostavka")
ACTIVE_RIDE_STATUSES = (
    "pending",
    "accepted",
    "arrived",
    "ongoing",
    "arrived_store",
    "pickup_requested",
    "in_delivery",
    "arrived_customer",
    "delivered_waiting_customer",
)
RIDE_STATUSES = (*ACTIVE_RIDE_STATUSES, "completed", "canceled")
DRIVER_ACTIVE_STATUSES = ACTIVE_RIDE_STATUSES[1:]


class TaxiDriver(Base):
    __tablename__ = "taxi_drivers"
    __table_args__ = (
        CheckConstraint(
            "service IN ('taxi','dostavka','both')",
            name="ck_taxi_drivers_service",
        ),
        CheckConstraint("rating_sum >= 0", name="ck_taxi_drivers_rating_sum"),
        CheckConstraint("rating_count >= 0", name="ck_taxi_drivers_rating_count"),
        CheckConstraint("balance >= 0", name="ck_taxi_drivers_balance"),
        CheckConstraint("status IN ('active','blocked')", name="ck_taxi_drivers_status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    user_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    phone: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    car_model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    car_color: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    car_plate: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    service: Mapped[str] = mapped_column(String(16), nullable=False, default="taxi")
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rating_sum: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    rating_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TaxiRide(Base):
    __tablename__ = "taxi_rides"
    __table_args__ = (
        CheckConstraint("kind IN ('taxi','dostavka')", name="ck_taxi_rides_kind"),
        CheckConstraint(
            "status IN ('pending','accepted','arrived','ongoing','arrived_store',"
            "'pickup_requested','in_delivery','arrived_customer',"
            "'delivered_waiting_customer','completed','canceled')",
            name="ck_taxi_rides_status",
        ),
        CheckConstraint(
            "from_lat IS NULL OR from_lat BETWEEN -90 AND 90",
            name="ck_taxi_rides_from_lat",
        ),
        CheckConstraint(
            "from_lng IS NULL OR from_lng BETWEEN -180 AND 180",
            name="ck_taxi_rides_from_lng",
        ),
        CheckConstraint(
            "to_lat IS NULL OR to_lat BETWEEN -90 AND 90",
            name="ck_taxi_rides_to_lat",
        ),
        CheckConstraint(
            "to_lng IS NULL OR to_lng BETWEEN -180 AND 180",
            name="ck_taxi_rides_to_lng",
        ),
        CheckConstraint("dist_km IS NULL OR dist_km >= 0", name="ck_taxi_rides_dist"),
        CheckConstraint("dur_min IS NULL OR dur_min >= 0", name="ck_taxi_rides_duration"),
        CheckConstraint("meter_km IS NULL OR meter_km >= 0", name="ck_taxi_rides_meter"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    customer_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    driver_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("taxi_drivers.id", ondelete="SET NULL"),
    )
    source_order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("orders.id", ondelete="SET NULL"),
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="taxi")
    from_addr: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    to_addr: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    from_lat: Mapped[float | None] = mapped_column(Float)
    from_lng: Mapped[float | None] = mapped_column(Float)
    to_lat: Mapped[float | None] = mapped_column(Float)
    to_lng: Mapped[float | None] = mapped_column(Float)
    dist_km: Mapped[float | None] = mapped_column(Float)
    dur_min: Mapped[int | None] = mapped_column(Integer)
    meter_km: Mapped[float | None] = mapped_column(Float)
    ozim: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cargo: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    car_type: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index("uq_taxi_drivers_user", TaxiDriver.user_account_id, unique=True)
Index(
    "uq_taxi_drivers_legacy_source",
    TaxiDriver.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index("ix_taxi_drivers_available_service", TaxiDriver.available, TaxiDriver.service)
Index("ix_taxi_rides_customer_created", TaxiRide.customer_account_id, TaxiRide.created_at)
Index("ix_taxi_rides_status_kind_created", TaxiRide.status, TaxiRide.kind, TaxiRide.created_at)
Index("ix_taxi_rides_driver_status", TaxiRide.driver_id, TaxiRide.status)
Index(
    "uq_taxi_rides_legacy_source",
    TaxiRide.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "uq_taxi_rides_source_order",
    TaxiRide.source_order_id,
    unique=True,
    postgresql_where=text("source_order_id IS NOT NULL"),
    sqlite_where=text("source_order_id IS NOT NULL"),
)
_ACTIVE_SQL = (
    "status IN ('pending','accepted','arrived','ongoing','arrived_store',"
    "'pickup_requested','in_delivery','arrived_customer',"
    "'delivered_waiting_customer') AND source_order_id IS NULL"
)
_DRIVER_ACTIVE_SQL = (
    "driver_id IS NOT NULL AND status IN ('accepted','arrived','ongoing',"
    "'arrived_store','pickup_requested','in_delivery','arrived_customer',"
    "'delivered_waiting_customer')"
)
Index(
    "uq_taxi_rides_active_customer",
    TaxiRide.customer_account_id,
    unique=True,
    postgresql_where=text(_ACTIVE_SQL),
    sqlite_where=text(_ACTIVE_SQL),
)
Index(
    "uq_taxi_rides_active_driver",
    TaxiRide.driver_id,
    unique=True,
    postgresql_where=text(_DRIVER_ACTIVE_SQL),
    sqlite_where=text(_DRIVER_ACTIVE_SQL),
)
