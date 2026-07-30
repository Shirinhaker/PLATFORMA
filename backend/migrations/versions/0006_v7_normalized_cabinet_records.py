"""V7 normalized cabinet records.

Revision ID: 0006_v7_cabinet_records
Revises: 0005_profile_cabinet_parity
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_v7_cabinet_records"
down_revision = "0005_profile_cabinet_parity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cabinet_normalization_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("schema_version", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("profiles_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("profiles_verified", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resources_source", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resources_target", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_source", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_target", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_digest", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("target_digest", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("error_code", sa.String(length=120), nullable=False, server_default=""),
    )

    op.create_table(
        "cabinet_resources",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_type", sa.String(length=16), nullable=False),
        sa.Column("resource", sa.String(length=96), nullable=False),
        sa.Column("value_kind", sa.String(length=16), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("digest", sa.String(length=64), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "account_id",
            "account_type",
            "resource",
            name="uq_cabinet_resources_owner_resource",
        ),
    )
    op.create_index(
        "ix_cabinet_resources_owner",
        "cabinet_resources",
        ["account_id", "account_type"],
        unique=False,
    )

    op.create_table(
        "cabinet_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "resource_id",
            sa.BigInteger(),
            sa.ForeignKey("cabinet_resources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_key", sa.String(length=160), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("value_kind", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "resource_id",
            "source_key",
            name="uq_cabinet_records_resource_source",
        ),
    )
    op.create_index(
        "ix_cabinet_records_resource_ordinal",
        "cabinet_records",
        ["resource_id", "ordinal"],
        unique=False,
    )

    op.create_table(
        "cabinet_record_fields",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "record_id",
            sa.BigInteger(),
            sa.ForeignKey("cabinet_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("value_type", sa.String(length=16), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_integer", sa.BigInteger(), nullable=True),
        sa.Column("value_float", sa.Float(), nullable=True),
        sa.Column("value_boolean", sa.Boolean(), nullable=True),
        sa.UniqueConstraint(
            "record_id",
            "path",
            name="uq_cabinet_record_fields_record_path",
        ),
    )
    op.create_index(
        "ix_cabinet_record_fields_record",
        "cabinet_record_fields",
        ["record_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_cabinet_record_fields_record", table_name="cabinet_record_fields")
    op.drop_table("cabinet_record_fields")
    op.drop_index("ix_cabinet_records_resource_ordinal", table_name="cabinet_records")
    op.drop_table("cabinet_records")
    op.drop_index("ix_cabinet_resources_owner", table_name="cabinet_resources")
    op.drop_table("cabinet_resources")
    op.drop_table("cabinet_normalization_runs")
