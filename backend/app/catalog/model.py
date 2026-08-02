from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.legacy_migration.model import (
    OWNER_STATE_ENUM,
    REVIEW_STATE_ENUM,
    OwnerState,
    ReviewState,
)


class CatalogGroup(Base):
    __tablename__ = "catalog_groups"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('product', 'service')",
            name="ck_catalog_groups_kind",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
    )
    source_record_key: Mapped[str | None] = mapped_column(String(160))
    owner_name_snapshot: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        default="",
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
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


class CatalogItem(Base):
    __tablename__ = "catalog_items"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('product', 'service')",
            name="ck_catalog_items_kind",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    business_account_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
    )
    source_record_key: Mapped[str | None] = mapped_column(String(160))
    catalog_group_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("catalog_groups.id", ondelete="SET NULL"),
    )
    owner_name_snapshot: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        default="",
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    price_text: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="",
    )
    unit: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="dona",
    )
    note: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
        default="",
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    queue_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    image_object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        default="",
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_state: Mapped[OwnerState] = mapped_column(
        OWNER_STATE_ENUM,
        nullable=False,
    )
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


Index(
    "ix_catalog_groups_live_source",
    CatalogGroup.business_account_id,
    CatalogGroup.source_record_key,
    unique=True,
)

Index(
    "ix_catalog_items_live_source",
    CatalogItem.business_account_id,
    CatalogItem.source_record_key,
    unique=True,
)

Index(
    "ix_catalog_items_catalog_group_id",
    CatalogItem.catalog_group_id,
)
