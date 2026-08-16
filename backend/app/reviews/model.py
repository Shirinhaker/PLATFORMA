from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
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


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint(
            "target_kind IN ('business', 'specialist')",
            name="ck_reviews_target_kind",
        ),
        CheckConstraint(
            "stars BETWEEN 1 AND 5",
            name="ck_reviews_stars",
        ),
        CheckConstraint(
            "reviewer_account_id <> target_account_id",
            name="ck_reviews_not_self",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    target_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    target_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("orders.id", ondelete="SET NULL"),
    )
    stars: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    owner_reply: Mapped[str] = mapped_column(Text, nullable=False, default="")
    owner_replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


Index(
    "uq_reviews_target_reviewer",
    Review.target_kind,
    Review.target_account_id,
    Review.reviewer_account_id,
    unique=True,
)
Index(
    "ix_reviews_target_created",
    Review.target_kind,
    Review.target_account_id,
    Review.created_at,
    Review.id,
)
Index("ix_reviews_reviewer", Review.reviewer_account_id, Review.id)
Index("ix_reviews_order", Review.order_id)
Index(
    "uq_reviews_legacy_source",
    Review.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
)
