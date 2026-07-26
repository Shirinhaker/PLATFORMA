from alembic import op
import sqlalchemy as sa


revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_outbox",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("topic", sa.String(length=120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("locked_by", sa.String(length=120)),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_platform_outbox_due",
        "platform_outbox",
        ["status", "available_at", "id"],
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("scope", sa.String(length=80), primary_key=True),
        sa.Column("key", sa.String(length=120), primary_key=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer()),
        sa.Column("response_body", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_idempotency_expiry",
        "idempotency_keys",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_table("platform_outbox")
