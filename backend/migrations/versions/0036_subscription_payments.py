"""Obuna va to'lov kabinetlarini typed domenga yakuniy o'tkazish.

Revision ID: 0036_subscription_payments
Revises: 0035_follow_lists

v1656 obuna tarixi `business_id = ? ORDER BY id DESC` bilan olinadi.
Yangi indeks aynan shu tenglik va tartib so'rovini qoplaydi.
"""

from alembic import op


revision = "0036_subscription_payments"
down_revision = "0035_follow_lists"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_business_subscriptions_history",
        "business_subscriptions",
        ["business_account_id", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_business_subscriptions_history",
        table_name="business_subscriptions",
    )
