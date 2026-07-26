from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Index,
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


Index(
    "uq_business_profiles_public_username_lower",
    func.lower(BusinessProfile.__table__.c.public_username),
    unique=True,
    postgresql_where=text("public_username <> ''"),
)
