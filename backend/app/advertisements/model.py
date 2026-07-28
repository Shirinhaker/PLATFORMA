from datetime import datetime, time
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Integer,
    JSON,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.legacy_migration.model import (
    REVIEW_STATE_ENUM,
    ReviewState,
)


class Advertisement(Base):
    __tablename__ = "advertisements"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    owner_user_account_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
    )
    owner_business_account_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
    )
    actor_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="business",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    caption: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
        default="",
    )
    desktop_image_object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        default="",
    )
    mobile_image_object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        default="",
    )
    crop_x: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    crop_y: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    crop_zoom: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    daily_all_day: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    daily_start: Mapped[time | None] = mapped_column(Time(timezone=False))
    daily_end: Mapped[time | None] = mapped_column(Time(timezone=False))
    targets_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    placement: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="home",
    )
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    district_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    hours_per_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    district_hour_rate: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )
    billable_district_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    price_code: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="",
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    views: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    clicks: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    review_state: Mapped[ReviewState] = mapped_column(
        REVIEW_STATE_ENUM,
        nullable=False,
    )
    migration_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("migration_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
