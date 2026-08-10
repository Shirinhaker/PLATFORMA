"""Obunachilar ro'yxatini typed follow domeniga yakuniy ko'chirish.

Revision ID: 0035_follow_lists
Revises: 0034_education_management

Obunachilar ro'yxati `created_at DESC, id DESC` tartibida olinadi. Nishon
bo'yicha kompozit indeks shu tenglik + tartib so'rovini qoplaydi.
"""

from alembic import op


revision = "0035_follow_lists"
down_revision = "0034_education_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_profile_follows_target", table_name="profile_follows")
    op.create_index(
        "ix_profile_follows_target",
        "profile_follows",
        ["target_account_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_profile_follows_target", table_name="profile_follows")
    op.create_index(
        "ix_profile_follows_target",
        "profile_follows",
        ["target_account_id", "id"],
    )
