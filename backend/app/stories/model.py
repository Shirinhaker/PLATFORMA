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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Story(Base):
    __tablename__ = "stories"
    __table_args__ = (
        CheckConstraint(
            "owner_type IN ('user', 'business')",
            name="ck_stories_owner_type",
        ),
        CheckConstraint(
            "media_type IN ('image', 'video')",
            name="ck_stories_media_type",
        ),
        CheckConstraint(
            "status IN ('processing', 'active', 'failed')",
            name="ck_stories_status",
        ),
        CheckConstraint(
            "duration_seconds >= 0 AND duration_seconds <= 60",
            name="ck_stories_duration",
        ),
        CheckConstraint(
            "length(caption) <= 200",
            name="ck_stories_caption_length",
        ),
        Index(
            "ix_stories_active_owner",
            "owner_account_id",
            "expires_at",
            "created_at",
            postgresql_where=text(
                "status IN ('processing', 'active') AND deleted_at IS NULL"
            ),
        ),
        Index(
            "ix_stories_feed_active",
            "expires_at",
            "owner_type",
            "owner_account_id",
            "created_at",
            postgresql_where=text(
                "status = 'active' AND deleted_at IS NULL"
            ),
        ),
        Index("ix_stories_creator_account", "created_by_account_id"),
        Index("ix_stories_creator_staff", "created_by_staff_id"),
        Index("ix_stories_migration_run", "migration_run_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    owner_type: Mapped[str] = mapped_column(String(16), nullable=False)
    owner_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_account_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
    )
    created_by_staff_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("staff_members.id", ondelete="SET NULL"),
    )
    media_type: Mapped[str] = mapped_column(String(16), nullable=False)
    media_object_key: Mapped[str] = mapped_column(
        String(1024), nullable=False, default=""
    )
    thumbnail_object_key: Mapped[str] = mapped_column(
        String(1024), nullable=False, default=""
    )
    source_object_key: Mapped[str] = mapped_column(
        String(1024), nullable=False, default=""
    )
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    caption: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="processing"
    )
    legacy_source_id: Mapped[int | None] = mapped_column(BigInteger)
    migration_run_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("migration_runs.id", ondelete="RESTRICT"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index(
    "uq_stories_legacy_source",
    Story.legacy_source_id,
    unique=True,
    postgresql_where=text("legacy_source_id IS NOT NULL"),
    sqlite_where=text("legacy_source_id IS NOT NULL"),
)


class StoryView(Base):
    __tablename__ = "story_views"
    __table_args__ = (
        UniqueConstraint(
            "story_id",
            "viewer_account_id",
            name="uq_story_views_story_viewer",
        ),
        Index(
            "ix_story_views_story_viewed",
            "story_id",
            "viewed_at",
        ),
        Index("ix_story_views_viewer", "viewer_account_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(),
        primary_key=True,
    )
    story_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("stories.id", ondelete="CASCADE"),
        nullable=False,
    )
    viewer_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class StoryReport(Base):
    __tablename__ = "story_reports"
    __table_args__ = (
        UniqueConstraint(
            "story_id",
            "reporter_account_id",
            name="uq_story_reports_story_reporter",
        ),
        CheckConstraint(
            "status IN ('new', 'reviewed', 'dismissed')",
            name="ck_story_reports_status",
        ),
        CheckConstraint(
            "length(reason) >= 10 AND length(reason) <= 300",
            name="ck_story_reports_reason_length",
        ),
        Index(
            "ix_story_reports_status_created",
            "status",
            "created_at",
        ),
        Index("ix_story_reports_reporter", "reporter_account_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    story_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("stories.id", ondelete="CASCADE"),
        nullable=False,
    )
    reporter_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
