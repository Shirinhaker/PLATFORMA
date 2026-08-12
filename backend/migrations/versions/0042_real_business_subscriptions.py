"""Make legacy subscription reconciliation concurrency-safe.

Revision ID: 0042_real_business_subscriptions
Revises: 0041_taxi_driver_domain
"""

from alembic import op
import sqlalchemy as sa


revision = "0042_real_business_subscriptions"
down_revision = "0041_taxi_driver_domain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_business_subscriptions_legacy",
        "business_subscriptions",
        ["legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
        sqlite_where=sa.text("legacy_source_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_business_subscriptions_legacy",
        table_name="business_subscriptions",
    )
