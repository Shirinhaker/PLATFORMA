"""v1656 24 soatlik Istoriyalar domeni.

Revision ID: 0030_stories
Revises: 0029_listing_publish_price
"""

from alembic import op
import sqlalchemy as sa


revision = "0030_stories"
down_revision = "0029_listing_publish_price"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stories",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("owner_type", sa.String(length=16), nullable=False),
        sa.Column("owner_account_id", sa.BigInteger(), nullable=False),
        sa.Column("created_by_account_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by_staff_id", sa.BigInteger(), nullable=True),
        sa.Column("media_type", sa.String(length=16), nullable=False),
        sa.Column(
            "media_object_key", sa.String(length=1024), nullable=False,
            server_default="",
        ),
        sa.Column(
            "thumbnail_object_key", sa.String(length=1024), nullable=False,
            server_default="",
        ),
        sa.Column(
            "source_object_key", sa.String(length=1024), nullable=False,
            server_default="",
        ),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column(
            "caption", sa.String(length=200), nullable=False, server_default=""
        ),
        sa.Column(
            "duration_seconds", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column(
            "status", sa.String(length=16), nullable=False,
            server_default="processing",
        ),
        sa.Column("legacy_source_id", sa.BigInteger(), nullable=True),
        sa.Column("migration_run_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "owner_type IN ('user', 'business')",
            name="ck_stories_owner_type",
        ),
        sa.CheckConstraint(
            "media_type IN ('image', 'video')",
            name="ck_stories_media_type",
        ),
        sa.CheckConstraint(
            "status IN ('processing', 'active', 'failed')",
            name="ck_stories_status",
        ),
        sa.CheckConstraint(
            "duration_seconds >= 0 AND duration_seconds <= 60",
            name="ck_stories_duration",
        ),
        sa.CheckConstraint(
            "length(caption) <= 200",
            name="ck_stories_caption_length",
        ),
        sa.ForeignKeyConstraint(
            ["owner_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_account_id"], ["accounts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_staff_id"], ["staff_members.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["migration_run_id"], ["migration_runs.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "uq_stories_legacy_source",
        "stories",
        ["legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "ix_stories_active_owner",
        "stories",
        ["owner_account_id", "expires_at", "created_at"],
        postgresql_where=sa.text(
            "status IN ('processing', 'active') AND deleted_at IS NULL"
        ),
    )
    op.create_index(
        "ix_stories_feed_active",
        "stories",
        ["expires_at", "owner_type", "owner_account_id", "created_at"],
        postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_stories_creator_account", "stories", ["created_by_account_id"]
    )
    op.create_index(
        "ix_stories_creator_staff", "stories", ["created_by_staff_id"]
    )
    op.create_index(
        "ix_stories_migration_run", "stories", ["migration_run_id"]
    )

    op.create_table(
        "story_views",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("story_id", sa.BigInteger(), nullable=False),
        sa.Column("viewer_account_id", sa.BigInteger(), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["story_id"], ["stories.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["viewer_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "story_id", "viewer_account_id",
            name="uq_story_views_story_viewer",
        ),
    )
    op.create_index(
        "ix_story_views_story_viewed",
        "story_views",
        ["story_id", "viewed_at"],
    )
    op.create_index(
        "ix_story_views_viewer", "story_views", ["viewer_account_id"]
    )

    op.create_table(
        "story_reports",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("story_id", sa.BigInteger(), nullable=False),
        sa.Column("reporter_account_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="new"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('new', 'reviewed', 'dismissed')",
            name="ck_story_reports_status",
        ),
        sa.CheckConstraint(
            "length(reason) >= 10 AND length(reason) <= 300",
            name="ck_story_reports_reason_length",
        ),
        sa.ForeignKeyConstraint(
            ["story_id"], ["stories.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reporter_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "story_id", "reporter_account_id",
            name="uq_story_reports_story_reporter",
        ),
    )
    op.create_index(
        "ix_story_reports_status_created",
        "story_reports",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_story_reports_reporter", "story_reports", ["reporter_account_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_story_reports_reporter", table_name="story_reports")
    op.drop_index(
        "ix_story_reports_status_created", table_name="story_reports"
    )
    op.drop_table("story_reports")
    op.drop_index("ix_story_views_viewer", table_name="story_views")
    op.drop_index("ix_story_views_story_viewed", table_name="story_views")
    op.drop_table("story_views")
    op.drop_index("ix_stories_migration_run", table_name="stories")
    op.drop_index("ix_stories_creator_staff", table_name="stories")
    op.drop_index("ix_stories_creator_account", table_name="stories")
    op.drop_index("ix_stories_feed_active", table_name="stories")
    op.drop_index("ix_stories_active_owner", table_name="stories")
    op.drop_index("uq_stories_legacy_source", table_name="stories")
    op.drop_table("stories")
