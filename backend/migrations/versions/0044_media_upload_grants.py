"""Presigned media upload orphanlarini kuzatish.

Revision ID: 0044_media_upload_grants
Revises: 0043_public_search_trgm
"""

import sqlalchemy as sa
from alembic import op


revision = "0044_media_upload_grants"
down_revision = "0043_public_search_trgm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_upload_grants",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("owner_account_id", sa.BigInteger(), nullable=False),
        sa.Column("owner_type", sa.String(20), nullable=False),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("object_key", sa.String(700), nullable=False, unique=True),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("declared_size", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attached_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_media_upload_grants_cleanup",
        "media_upload_grants",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_media_upload_grants_cleanup", table_name="media_upload_grants")
    op.drop_table("media_upload_grants")
