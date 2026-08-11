"""Create typed Taxi, delivery, and driver tables.

Revision ID: 0041_taxi_driver_domain
Revises: 0040_ai_assistant_domain
"""

from alembic import op
import sqlalchemy as sa


revision = "0041_taxi_driver_domain"
down_revision = "0040_ai_assistant_domain"
branch_labels = None
depends_on = None


ACTIVE = (
    "status IN ('pending','accepted','arrived','ongoing','arrived_store',"
    "'pickup_requested','in_delivery','arrived_customer',"
    "'delivered_waiting_customer') AND source_order_id IS NULL"
)
DRIVER_ACTIVE = (
    "driver_id IS NOT NULL AND status IN ('accepted','arrived','ongoing',"
    "'arrived_store','pickup_requested','in_delivery','arrived_customer',"
    "'delivered_waiting_customer')"
)


def upgrade() -> None:
    op.create_table(
        "taxi_drivers",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("legacy_source_id", sa.BigInteger(), nullable=True),
        sa.Column("user_account_id", sa.BigInteger(), nullable=False),
        sa.Column("phone", sa.String(80), nullable=False, server_default=""),
        sa.Column("car_model", sa.String(120), nullable=False, server_default=""),
        sa.Column("car_color", sa.String(80), nullable=False, server_default=""),
        sa.Column("car_plate", sa.String(40), nullable=False, server_default=""),
        sa.Column("service", sa.String(16), nullable=False, server_default="taxi"),
        sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("rating_sum", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rating_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("service IN ('taxi','dostavka','both')", name="ck_taxi_drivers_service"),
        sa.CheckConstraint("rating_sum >= 0", name="ck_taxi_drivers_rating_sum"),
        sa.CheckConstraint("rating_count >= 0", name="ck_taxi_drivers_rating_count"),
        sa.CheckConstraint("balance >= 0", name="ck_taxi_drivers_balance"),
        sa.CheckConstraint("status IN ('active','blocked')", name="ck_taxi_drivers_status"),
        sa.ForeignKeyConstraint(["user_account_id"], ["accounts.id"], ondelete="CASCADE"),
    )
    op.create_index("uq_taxi_drivers_user", "taxi_drivers", ["user_account_id"], unique=True)
    op.create_index(
        "uq_taxi_drivers_legacy_source",
        "taxi_drivers",
        ["legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "ix_taxi_drivers_available_service",
        "taxi_drivers",
        ["available", "service"],
    )

    op.create_table(
        "taxi_rides",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("legacy_source_id", sa.BigInteger(), nullable=True),
        sa.Column("customer_account_id", sa.BigInteger(), nullable=False),
        sa.Column("driver_id", sa.BigInteger(), nullable=True),
        sa.Column("source_order_id", sa.BigInteger(), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False, server_default="taxi"),
        sa.Column("from_addr", sa.String(500), nullable=False, server_default=""),
        sa.Column("to_addr", sa.String(500), nullable=False, server_default=""),
        sa.Column("from_lat", sa.Float(), nullable=True),
        sa.Column("from_lng", sa.Float(), nullable=True),
        sa.Column("to_lat", sa.Float(), nullable=True),
        sa.Column("to_lng", sa.Float(), nullable=True),
        sa.Column("dist_km", sa.Float(), nullable=True),
        sa.Column("dur_min", sa.Integer(), nullable=True),
        sa.Column("meter_km", sa.Float(), nullable=True),
        sa.Column("ozim", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cargo", sa.String(500), nullable=False, server_default=""),
        sa.Column("car_type", sa.String(80), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('taxi','dostavka')", name="ck_taxi_rides_kind"),
        sa.CheckConstraint(
            "status IN ('pending','accepted','arrived','ongoing','arrived_store',"
            "'pickup_requested','in_delivery','arrived_customer',"
            "'delivered_waiting_customer','completed','canceled')",
            name="ck_taxi_rides_status",
        ),
        sa.CheckConstraint("from_lat IS NULL OR from_lat BETWEEN -90 AND 90", name="ck_taxi_rides_from_lat"),
        sa.CheckConstraint("from_lng IS NULL OR from_lng BETWEEN -180 AND 180", name="ck_taxi_rides_from_lng"),
        sa.CheckConstraint("to_lat IS NULL OR to_lat BETWEEN -90 AND 90", name="ck_taxi_rides_to_lat"),
        sa.CheckConstraint("to_lng IS NULL OR to_lng BETWEEN -180 AND 180", name="ck_taxi_rides_to_lng"),
        sa.CheckConstraint("dist_km IS NULL OR dist_km >= 0", name="ck_taxi_rides_dist"),
        sa.CheckConstraint("dur_min IS NULL OR dur_min >= 0", name="ck_taxi_rides_duration"),
        sa.CheckConstraint("meter_km IS NULL OR meter_km >= 0", name="ck_taxi_rides_meter"),
        sa.ForeignKeyConstraint(["customer_account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["driver_id"], ["taxi_drivers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_order_id"], ["orders.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_taxi_rides_customer_created", "taxi_rides", ["customer_account_id", "created_at"])
    op.create_index("ix_taxi_rides_status_kind_created", "taxi_rides", ["status", "kind", "created_at"])
    op.create_index("ix_taxi_rides_driver_status", "taxi_rides", ["driver_id", "status"])
    op.create_index(
        "uq_taxi_rides_legacy_source", "taxi_rides", ["legacy_source_id"],
        unique=True, postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "uq_taxi_rides_source_order", "taxi_rides", ["source_order_id"],
        unique=True, postgresql_where=sa.text("source_order_id IS NOT NULL"),
    )
    op.create_index(
        "uq_taxi_rides_active_customer", "taxi_rides", ["customer_account_id"],
        unique=True, postgresql_where=sa.text(ACTIVE),
    )
    op.create_index(
        "uq_taxi_rides_active_driver", "taxi_rides", ["driver_id"],
        unique=True, postgresql_where=sa.text(DRIVER_ACTIVE),
    )


def downgrade() -> None:
    op.drop_table("taxi_rides")
    op.drop_table("taxi_drivers")
