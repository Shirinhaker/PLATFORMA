from alembic import op
import sqlalchemy as sa


revision = "0005_profile_cabinet_parity"
down_revision = "0004_shared_login_cabinets"
branch_labels = None
depends_on = None


def json_column(name: str, default: str):
    return sa.Column(
        name,
        sa.JSON(),
        nullable=False,
        server_default=sa.text(f"'{default}'::json"),
    )


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("followers_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("user_profiles", sa.Column("following_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("user_profiles", sa.Column("has_business", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("user_profiles", json_column("dashboard_snapshot", "{}"))
    op.add_column("user_profiles", json_column("recent_activity", "[]"))
    op.add_column("user_profiles", json_column("specialist_profile", "{}"))
    op.add_column("user_profiles", json_column("cabinet_payload", "{}"))

    op.add_column("business_profiles", sa.Column("followers_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("business_profiles", sa.Column("following_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("business_profiles", sa.Column("rating_sum", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("business_profiles", sa.Column("rating_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("business_profiles", sa.Column("map_visible", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("business_profiles", json_column("dashboard_snapshot", "{}"))
    op.add_column("business_profiles", json_column("recent_activity", "[]"))
    op.add_column("business_profiles", json_column("cabinet_payload", "{}"))

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
        "cabinet_payload",
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
        "cabinet_payload",
        "specialist_profile",
        "recent_activity",
        "dashboard_snapshot",
        "has_business",
        "following_count",
        "followers_count",
    ):
        op.drop_column("user_profiles", column)
