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


class SpecialistProfile(Base):
    __tablename__ = "specialist_profiles"
    __table_args__ = (
        CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name="ck_specialist_profiles_latitude",
        ),
        CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name="ck_specialist_profiles_longitude",
        ),
    )

    user_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    profession: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price_text: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    service_area: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    is_government: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    organization: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    department: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    position: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    work_hours: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    after_hours: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class SpecialistCredential(Base):
    __tablename__ = "specialist_credentials"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    user_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    object_key: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    legacy_media_url: Mapped[str] = mapped_column(
        String(2048), nullable=False, default=""
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class SpecialistOffer(Base):
    __tablename__ = "specialist_offers"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('service', 'product')",
            name="ck_specialist_offers_kind",
        ),
        CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_specialist_offers_name_required",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    user_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(12), nullable=False, default="service")
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    price_text: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    note: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    image_object_key: Mapped[str] = mapped_column(
        String(600), nullable=False, default=""
    )
    legacy_image_url: Mapped[str] = mapped_column(
        String(2048), nullable=False, default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class SpecialistPortfolio(Base):
    __tablename__ = "specialist_portfolio"
    __table_args__ = (
        CheckConstraint(
            "media_type IN ('photo', 'video')",
            name="ck_specialist_portfolio_media_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    user_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    media_type: Mapped[str] = mapped_column(String(12), nullable=False, default="photo")
    object_key: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    legacy_media_url: Mapped[str] = mapped_column(
        String(2048), nullable=False, default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


Index(
    "ix_specialist_profiles_visible_location",
    SpecialistProfile.visible,
    SpecialistProfile.latitude,
    SpecialistProfile.longitude,
)
Index(
    "ix_specialist_credentials_user_position",
    SpecialistCredential.user_account_id,
    SpecialistCredential.position,
    SpecialistCredential.id,
)
Index(
    "uq_specialist_credentials_user_legacy",
    SpecialistCredential.user_account_id,
    SpecialistCredential.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "ix_specialist_offers_user_created",
    SpecialistOffer.user_account_id,
    SpecialistOffer.created_at,
    SpecialistOffer.id,
)
Index(
    "uq_specialist_offers_user_legacy",
    SpecialistOffer.user_account_id,
    SpecialistOffer.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
Index(
    "ix_specialist_portfolio_user_created",
    SpecialistPortfolio.user_account_id,
    SpecialistPortfolio.created_at,
    SpecialistPortfolio.id,
)
Index(
    "uq_specialist_portfolio_user_legacy",
    SpecialistPortfolio.user_account_id,
    SpecialistPortfolio.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)
