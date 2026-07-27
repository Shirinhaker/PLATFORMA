from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_auth_profiles"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


account_type_enum = postgresql.ENUM(
    "user",
    "business",
    name="account_type",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE TYPE account_type AS ENUM ('user', 'business')")

    op.create_table(
        "accounts",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
        ),
        sa.Column("account_type", account_type_enum, nullable=False),
        sa.Column("login", sa.String(length=80), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger()),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_accounts_telegram_type",
        "accounts",
        ["telegram_user_id", "account_type"],
        unique=True,
        postgresql_where=sa.text("telegram_user_id IS NOT NULL"),
    )

    op.create_table(
        "pending_registrations",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
        ),
        sa.Column("account_type", account_type_enum, nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_pending_registrations_expires_at",
        "pending_registrations",
        ["expires_at"],
    )

    op.create_table(
        "auth_challenges",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
        ),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "pending_registration_id",
            sa.BigInteger(),
            sa.ForeignKey("pending_registrations.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "start_token_hash",
            sa.String(length=64),
            nullable=False,
            unique=True,
        ),
        sa.Column("telegram_user_id", sa.BigInteger()),
        sa.Column(
            "code_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("code_hash", sa.String(length=64)),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "max_attempts",
            sa.Integer(),
            nullable=False,
            server_default="5",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("code_sent_at", sa.DateTime(timezone=True)),
        sa.Column("code_expires_at", sa.DateTime(timezone=True)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_auth_challenges_start_expires_at",
        "auth_challenges",
        ["start_expires_at"],
    )
    op.create_index(
        "ix_auth_challenges_code_expires_at",
        "auth_challenges",
        ["code_expires_at"],
    )

    op.create_table(
        "auth_sessions",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
        ),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "token_hash",
            sa.String(length=64),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "device_name",
            sa.String(length=200),
            nullable=False,
            server_default="",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_auth_sessions_active_account",
        "auth_sessions",
        ["account_id", "expires_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "user_profiles",
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False, server_default=""),
        sa.Column(
            "public_username",
            sa.String(length=32),
            nullable=False,
            server_default="",
        ),
        sa.Column("region", sa.String(length=120), nullable=False, server_default=""),
        sa.Column(
            "district",
            sa.String(length=120),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "mahalla",
            sa.String(length=160),
            nullable=False,
            server_default="",
        ),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column(
            "location_exact",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "avatar_object_key",
            sa.String(length=1024),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "avatar_x",
            sa.Float(),
            nullable=False,
            server_default="50",
        ),
        sa.Column(
            "avatar_y",
            sa.Float(),
            nullable=False,
            server_default="50",
        ),
        sa.Column(
            "avatar_zoom",
            sa.Float(),
            nullable=False,
            server_default="1",
        ),
    )
    op.create_index(
        "uq_user_profiles_public_username_lower",
        "user_profiles",
        [sa.text("lower(public_username)")],
        unique=True,
        postgresql_where=sa.text("public_username <> ''"),
    )

    op.create_table(
        "business_profiles",
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False, server_default=""),
        sa.Column(
            "description",
            sa.String(length=2000),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "public_username",
            sa.String(length=32),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "direction",
            sa.String(length=120),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "activity_type",
            sa.String(length=120),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "address",
            sa.String(length=300),
            nullable=False,
            server_default="",
        ),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column(
            "work_hours",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "pay_card",
            sa.String(length=64),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "pay_holder",
            sa.String(length=160),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "pay_qr_object_key",
            sa.String(length=1024),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "director",
            sa.String(length=160),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "tax_id",
            sa.String(length=32),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "logo_object_key",
            sa.String(length=1024),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "logo_x",
            sa.Float(),
            nullable=False,
            server_default="50",
        ),
        sa.Column(
            "logo_y",
            sa.Float(),
            nullable=False,
            server_default="50",
        ),
        sa.Column(
            "logo_zoom",
            sa.Float(),
            nullable=False,
            server_default="1",
        ),
    )
    op.create_index(
        "uq_business_profiles_public_username_lower",
        "business_profiles",
        [sa.text("lower(public_username)")],
        unique=True,
        postgresql_where=sa.text("public_username <> ''"),
    )


def downgrade() -> None:
    op.drop_table("business_profiles")
    op.drop_table("user_profiles")
    op.drop_table("auth_sessions")
    op.drop_table("auth_challenges")
    op.drop_table("pending_registrations")
    op.drop_table("accounts")
    op.execute("DROP TYPE account_type")
