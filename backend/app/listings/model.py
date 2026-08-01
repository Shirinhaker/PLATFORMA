from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.legacy_migration.model import (
    REVIEW_STATE_ENUM,
    ReviewState,
)


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        Index(
            "uq_listings_business_source",
            "owner_business_account_id",
            "source_record_key",
            unique=True,
        ),
        Index(
            "ix_listings_public_v1656",
            "category",
            "status",
            "visibility",
            "review_state",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    owner_user_account_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
    )
    owner_business_account_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
    )
    source_record_key: Mapped[str | None] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        default="",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    price_text: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="",
    )
    description: Mapped[str] = mapped_column(
        String(4000),
        nullable=False,
        default="",
    )
    address: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        default="",
    )
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    visibility: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="all",
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    review_state: Mapped[ReviewState] = mapped_column(
        REVIEW_STATE_ENUM,
        nullable=False,
    )
    migration_run_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("migration_runs.id", ondelete="RESTRICT"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class ListingMedia(Base):
    __tablename__ = "listing_media"
    __table_args__ = (
        CheckConstraint(
            "media_type IN ('photo', 'video')",
            name="ck_listing_media_type",
        ),
        UniqueConstraint(
            "listing_id",
            "position",
            name="uq_listing_media_position",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)
    object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        default="",
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    migration_state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )
    migration_run_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("migration_runs.id", ondelete="RESTRICT"),
    )


class ListingSave(Base):
    __tablename__ = "listing_saves"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_account_id",
            "listing_id",
            name="uq_listing_saves_owner_listing",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    owner_user_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    listing_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
