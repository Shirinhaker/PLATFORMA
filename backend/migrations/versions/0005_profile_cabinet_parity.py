from alembic import op
import sqlalchemy as sa


revision = "0005_profile_cabinet_parity"
down_revision = "0004_shared_login_cabinets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("followers_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_profiles",
        sa.Column("following_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_profiles",
        sa.Column("has_business", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "user_profiles",
        sa.Column("dashboard_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.add_column(
        "user_profiles",
        sa.Column("recent_activity", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "user_profiles",
        sa.Column("specialist_profile", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )

    op.add_column(
        "business_profiles",
        sa.Column("followers_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "business_profiles",
        sa.Column("following_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "business_profiles",
        sa.Column("rating_sum", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "business_profiles",
        sa.Column("rating_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "business_profiles",
        sa.Column("map_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "business_profiles",
        sa.Column("dashboard_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.add_column(
        "business_profiles",
        sa.Column("recent_activity", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )

    op.create_table(
        "profile_links",
        sa.Column(
            "user_account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "business_account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("profile_links")
    for column in (
        "recent_activity",
        "dashboard_snapshot",
        "map_visible",
        "rating_count",
        "rating_sum",
        "following_count",
        "followers_count",
    ):
        op.drop_column("business_profiles", column)
    for column in (
        "specialist_profile",
        "recent_activity",
        "dashboard_snapshot",
        "has_business",
        "following_count",
        "followers_count",
    ):
        op.drop_column("user_profiles", column)
