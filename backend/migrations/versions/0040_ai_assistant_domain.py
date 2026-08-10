"""AI yordamchini typed PostgreSQL domeniga ko'chirish.

Revision ID: 0040_ai_assistant_domain
Revises: 0039_specialists_domain
"""

from alembic import op
import sqlalchemy as sa


revision = "0040_ai_assistant_domain"
down_revision = "0039_specialists_domain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_chat_messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False, server_default="local"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user','assistant')", name="ck_ai_chat_messages_role"),
        sa.CheckConstraint("length(trim(text)) > 0", name="ck_ai_chat_messages_text"),
    )
    op.create_index("ix_ai_chat_messages_business_created", "ai_chat_messages", ["business_account_id", "created_at", "id"])
    op.create_index("uq_ai_chat_messages_business_legacy", "ai_chat_messages", ["business_account_id", "legacy_source_id"], unique=True, postgresql_where=sa.text("legacy_source_id IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("uq_ai_chat_messages_business_legacy", table_name="ai_chat_messages")
    op.drop_index("ix_ai_chat_messages_business_created", table_name="ai_chat_messages")
    op.drop_table("ai_chat_messages")
