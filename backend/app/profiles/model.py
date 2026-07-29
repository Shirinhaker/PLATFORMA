from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    public_username: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="",
    )
    region: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    district: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    mahalla: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_exact: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    avatar_object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        default="",
    )
    avatar_x: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    avatar_y: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    avatar_zoom: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    followers_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    following_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_business: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dashboard_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    recent_activity: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    specialist_profile: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )


Index(
    "uq_user_profiles_public_username_lower",
    func.lower(UserProfile.__table__.c.public_username),
    unique=True,
    postgresql_where=text("public_username <> ''"),
)


class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    description: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
        default="",
    )
    public_username: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="",
    )
    direction: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="",
    )
    activity_type: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="",
    )
    address: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    work_hours: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    pay_card: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    pay_holder: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        default="",
    )
    pay_qr_object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        default="",
    )
    director: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        default="",
    )
    tax_id: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    logo_object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        default="",
    )
    logo_x: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    logo_y: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    logo_zoom: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    followers_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    following_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rating_sum: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    map_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dashboard_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    recent_activity: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )


Index(
    "uq_business_profiles_public_username_lower",
    func.lower(BusinessProfile.__table__.c.public_username),
    unique=True,
    postgresql_where=text("public_username <> ''"),
)


class ProfileLink(Base):
    __tablename__ = "profile_links"

    user_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    business_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
