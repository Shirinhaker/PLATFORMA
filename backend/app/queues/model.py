from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


IDENTITY_BIGINT = BigInteger().with_variant(Integer, "sqlite")
ACTIVE_QUEUE_SQL = "status IN ('waiting', 'called', 'in_service')"


class QueueProvider(Base):
    __tablename__ = "queue_providers"
    __table_args__ = (
        CheckConstraint(
            "experience_years >= 0",
            name="ck_queue_providers_experience_years",
        ),
        CheckConstraint(
            "avg_minutes BETWEEN 5 AND 240",
            name="ck_queue_providers_avg_minutes",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_queue_providers_status",
        ),
        CheckConstraint(
            "mode IN ('live', 'slot')",
            name="ck_queue_providers_mode",
        ),
    )

    id: Mapped[int] = mapped_column(IDENTITY_BIGINT, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    legacy_staff_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    staff_name_snapshot: Mapped[str] = mapped_column(
        String(120), nullable=False, default=""
    )
    profession_snapshot: Mapped[str] = mapped_column(
        String(120), nullable=False, default="Xodim"
    )
    specialty: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    experience_years: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qualification: Mapped[str] = mapped_column(
        String(100), nullable=False, default=""
    )
    work_days: Mapped[str] = mapped_column(
        String(30), nullable=False, default="1,2,3,4,5,6"
    )
    work_start: Mapped[time] = mapped_column(Time, nullable=False)
    work_end: Mapped[time] = mapped_column(Time, nullable=False)
    avg_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    room: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    bio: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    mode: Mapped[str] = mapped_column(String(8), nullable=False, default="live")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class QueueProviderService(Base):
    __tablename__ = "queue_provider_services"
    __table_args__ = (
        CheckConstraint(
            "duration_minutes BETWEEN 5 AND 240",
            name="ck_queue_provider_services_duration",
        ),
    )

    id: Mapped[int] = mapped_column(IDENTITY_BIGINT, Identity(), primary_key=True)
    provider_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("queue_providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    catalog_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("catalog_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=20
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class QueueEntry(Base):
    __tablename__ = "queue_entries"
    __table_args__ = (
        CheckConstraint(
            "source IN ('online', 'offline')",
            name="ck_queue_entries_source",
        ),
        CheckConstraint(
            "status IN ('waiting', 'called', 'in_service', 'done', "
            "'no_show', 'cancelled', 'skipped')",
            name="ck_queue_entries_status",
        ),
    )

    id: Mapped[int] = mapped_column(IDENTITY_BIGINT, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    catalog_item_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("catalog_items.id", ondelete="SET NULL"),
    )
    provider_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("queue_providers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_account_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
    )
    patient_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    service_name_snapshot: Mapped[str] = mapped_column(
        String(160), nullable=False, default=""
    )
    provider_name_snapshot: Mapped[str] = mapped_column(
        String(120), nullable=False, default=""
    )
    queue_date: Mapped[date] = mapped_column(Date, nullable=False)
    queue_no: Mapped[int] = mapped_column(Integer, nullable=False)
    queue_code: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(12), nullable=False, default="online")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="waiting")
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    slot_time: Mapped[time | None] = mapped_column(Time)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class QueueHistory(Base):
    __tablename__ = "queue_history"

    id: Mapped[int] = mapped_column(IDENTITY_BIGINT, Identity(), primary_key=True)
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    queue_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("queue_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    old_value: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    new_value: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    actor_account_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
    )
    legacy_actor_staff_id: Mapped[int | None] = mapped_column(BigInteger)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class QueueCounter(Base):
    __tablename__ = "queue_counters"
    __table_args__ = (
        CheckConstraint(
            "last_number >= 0",
            name="ck_queue_counters_last_number",
        ),
    )

    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    catalog_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("catalog_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    provider_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("queue_providers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    queue_date: Mapped[date] = mapped_column(Date, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


Index(
    "uq_queue_providers_business_staff",
    QueueProvider.business_account_id,
    QueueProvider.legacy_staff_id,
    unique=True,
)
Index(
    "uq_queue_providers_business_legacy",
    QueueProvider.business_account_id,
    QueueProvider.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "ix_queue_providers_business_status",
    QueueProvider.business_account_id,
    QueueProvider.status,
    QueueProvider.staff_name_snapshot,
)
Index(
    "uq_queue_provider_services_provider_item",
    QueueProviderService.provider_id,
    QueueProviderService.catalog_item_id,
    unique=True,
)
Index(
    "ix_queue_provider_services_item_active",
    QueueProviderService.catalog_item_id,
    QueueProviderService.active,
    QueueProviderService.provider_id,
)
Index(
    "uq_queue_entries_business_legacy",
    QueueEntry.business_account_id,
    QueueEntry.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "uq_queue_entries_number",
    QueueEntry.business_account_id,
    QueueEntry.catalog_item_id,
    QueueEntry.provider_id,
    QueueEntry.queue_date,
    QueueEntry.queue_no,
    unique=True,
)
Index(
    "uq_queue_entries_slot",
    QueueEntry.business_account_id,
    QueueEntry.catalog_item_id,
    QueueEntry.provider_id,
    QueueEntry.queue_date,
    QueueEntry.slot_time,
    unique=True,
    postgresql_where=text("slot_time IS NOT NULL"),
    sqlite_where=text("slot_time IS NOT NULL"),
)
Index(
    "uq_queue_entries_active_customer_live",
    QueueEntry.business_account_id,
    QueueEntry.catalog_item_id,
    QueueEntry.provider_id,
    QueueEntry.queue_date,
    QueueEntry.customer_account_id,
    unique=True,
    postgresql_where=text(
        f"customer_account_id IS NOT NULL AND slot_time IS NULL AND {ACTIVE_QUEUE_SQL}"
    ),
    sqlite_where=text(
        f"customer_account_id IS NOT NULL AND slot_time IS NULL AND {ACTIVE_QUEUE_SQL}"
    ),
)
Index(
    "ix_queue_entries_business_day",
    QueueEntry.business_account_id,
    QueueEntry.queue_date,
    QueueEntry.provider_id,
    QueueEntry.catalog_item_id,
    QueueEntry.queue_no,
)
Index(
    "ix_queue_entries_ahead",
    QueueEntry.provider_id,
    QueueEntry.catalog_item_id,
    QueueEntry.queue_date,
    QueueEntry.status,
    QueueEntry.queue_no,
)
Index(
    "ix_queue_entries_customer_created",
    QueueEntry.customer_account_id,
    QueueEntry.queue_date,
    QueueEntry.created_at,
    QueueEntry.id,
)
Index(
    "ix_queue_entries_catalog_item_id",
    QueueEntry.catalog_item_id,
)
Index(
    "ix_queue_history_queue",
    QueueHistory.queue_id,
    QueueHistory.id,
)
Index(
    "ix_queue_history_business_account_id",
    QueueHistory.business_account_id,
)
Index(
    "ix_queue_history_actor_account_id",
    QueueHistory.actor_account_id,
)
Index(
    "uq_queue_history_business_legacy",
    QueueHistory.business_account_id,
    QueueHistory.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "ix_queue_counters_catalog_item_id",
    QueueCounter.catalog_item_id,
)
Index(
    "ix_queue_counters_provider_id",
    QueueCounter.provider_id,
)
