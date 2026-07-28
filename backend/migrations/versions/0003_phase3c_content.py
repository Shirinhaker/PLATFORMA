from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003_phase3c_content"
down_revision = "0002_auth_profiles"
branch_labels = None
depends_on = None


owner_state_enum = postgresql.ENUM(
    "linked",
    "unlinked",
    name="owner_state",
    create_type=False,
)
review_state_enum = postgresql.ENUM(
    "ready",
    "review_required",
    name="review_state",
    create_type=False,
)
migration_environment_enum = postgresql.ENUM(
    "staging",
    "production",
    name="migration_environment",
    create_type=False,
)
migration_stage_enum = postgresql.ENUM(
    "snapshot",
    "inventory",
    "accounts",
    "businesses",
    "catalog",
    "listings",
    "advertisements",
    "media",
    "verify",
    name="migration_stage",
    create_type=False,
)
migration_status_enum = postgresql.ENUM(
    "pending",
    "running",
    "completed",
    "failed",
    name="migration_status",
    create_type=False,
)
media_migration_state_enum = postgresql.ENUM(
    "pending",
    "copied",
    "missing",
    "invalid",
    "failed",
    name="media_migration_state",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE TYPE owner_state AS ENUM ('linked', 'unlinked')")
    op.execute(
        "CREATE TYPE review_state AS ENUM ('ready', 'review_required')"
    )
    op.execute(
        "CREATE TYPE migration_environment AS ENUM ('staging', 'production')"
    )
    op.execute(
        "CREATE TYPE migration_stage AS ENUM ("
        "'snapshot', 'inventory', 'accounts', 'businesses', 'catalog', "
        "'listings', 'advertisements', 'media', 'verify')"
    )
    op.execute(
        "CREATE TYPE migration_status AS ENUM ("
        "'pending', 'running', 'completed', 'failed')"
    )
    op.execute(
        "CREATE TYPE media_migration_state AS ENUM ("
        "'pending', 'copied', 'missing', 'invalid', 'failed')"
    )

    op.create_table(
        "migration_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "source_database_sha256",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "media_manifest_sha256",
            sa.String(length=64),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "schema_version",
            sa.String(length=40),
            nullable=False,
            server_default="0003_phase3c_content",
        ),
        sa.Column(
            "environment",
            migration_environment_enum,
            nullable=False,
        ),
        sa.Column("stage", migration_stage_enum, nullable=False),
        sa.Column("status", migration_status_enum, nullable=False),
        sa.Column(
            "counters_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "error_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("approved_staging_run_id", sa.BigInteger()),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["approved_staging_run_id"],
            ["migration_runs.id"],
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "legacy_id_map",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("legacy_id", sa.BigInteger(), nullable=False),
        sa.Column("target_id", sa.BigInteger()),
        sa.Column("source_row_hash", sa.String(length=64), nullable=False),
        sa.Column("mapping_status", sa.String(length=40), nullable=False),
        sa.Column(
            "review_reason",
            sa.String(length=160),
            nullable=False,
            server_default="",
        ),
        sa.Column("last_run_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["last_run_id"],
            ["migration_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "entity_type",
            "legacy_id",
            name="uq_legacy_id_map",
        ),
    )

    op.create_table(
        "migration_issues",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("migration_run_id", sa.BigInteger(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("legacy_id", sa.BigInteger()),
        sa.Column("issue_code", sa.String(length=160), nullable=False),
        sa.Column(
            "details_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "resolved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["migration_run_id"],
            ["migration_runs.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_migration_issues_run_resolved",
        "migration_issues",
        ["migration_run_id", "resolved", "id"],
    )

    op.create_table(
        "media_migration",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("migration_run_id", sa.BigInteger(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("legacy_id", sa.BigInteger(), nullable=False),
        sa.Column("slot", sa.String(length=40), nullable=False),
        sa.Column(
            "source_reference_fingerprint",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "destination_object_key",
            sa.String(length=1024),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "sha256",
            sa.String(length=64),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "content_type",
            sa.String(length=120),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "size_bytes",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("state", media_migration_state_enum, nullable=False),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "last_error_code",
            sa.String(length=160),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["migration_run_id"],
            ["migration_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "entity_type",
            "legacy_id",
            "slot",
            name="uq_media_migration_source_slot",
        ),
    )
    op.create_index(
        "ix_media_migration_run_state",
        "media_migration",
        ["migration_run_id", "state", "id"],
    )

    op.create_table(
        "catalog_groups",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger()),
        sa.Column(
            "owner_name_snapshot",
            sa.String(length=160),
            nullable=False,
            server_default="",
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("review_state", review_state_enum, nullable=False),
        sa.Column("migration_run_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('product', 'service')",
            name="ck_catalog_groups_kind",
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"],
            ["accounts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["migration_run_id"],
            ["migration_runs.id"],
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "catalog_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger()),
        sa.Column("catalog_group_id", sa.BigInteger()),
        sa.Column(
            "owner_name_snapshot",
            sa.String(length=160),
            nullable=False,
            server_default="",
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "price_text",
            sa.String(length=120),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "note",
            sa.String(length=2000),
            nullable=False,
            server_default="",
        ),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column(
            "queue_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "image_object_key",
            sa.String(length=1024),
            nullable=False,
            server_default="",
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("owner_state", owner_state_enum, nullable=False),
        sa.Column("review_state", review_state_enum, nullable=False),
        sa.Column("migration_run_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('product', 'service')",
            name="ck_catalog_items_kind",
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"],
            ["accounts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_group_id"],
            ["catalog_groups.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["migration_run_id"],
            ["migration_runs.id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_catalog_items_public",
        "catalog_items",
        ["kind", "status", "review_state", "created_at", "id"],
    )

    op.create_table(
        "listings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("owner_user_account_id", sa.BigInteger()),
        sa.Column("owner_business_account_id", sa.BigInteger()),
        sa.Column(
            "category",
            sa.String(length=160),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "title",
            sa.String(length=200),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "price_text",
            sa.String(length=120),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "description",
            sa.String(length=4000),
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
            "visibility",
            sa.String(length=40),
            nullable=False,
            server_default="all",
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("review_state", review_state_enum, nullable=False),
        sa.Column("migration_run_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_account_id"],
            ["accounts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_business_account_id"],
            ["accounts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["migration_run_id"],
            ["migration_runs.id"],
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "listing_media",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("listing_id", sa.BigInteger(), nullable=False),
        sa.Column("media_type", sa.String(length=20), nullable=False),
        sa.Column(
            "object_key",
            sa.String(length=1024),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "migration_state",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("migration_run_id", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "media_type IN ('photo', 'video')",
            name="ck_listing_media_type",
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listings.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["migration_run_id"],
            ["migration_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "listing_id",
            "position",
            name="uq_listing_media_position",
        ),
    )

    op.create_table(
        "advertisements",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("owner_user_account_id", sa.BigInteger()),
        sa.Column("owner_business_account_id", sa.BigInteger()),
        sa.Column(
            "actor_type",
            sa.String(length=20),
            nullable=False,
            server_default="business",
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "caption",
            sa.String(length=2000),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "desktop_image_object_key",
            sa.String(length=1024),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "mobile_image_object_key",
            sa.String(length=1024),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "crop_x",
            sa.Float(),
            nullable=False,
            server_default="50",
        ),
        sa.Column(
            "crop_y",
            sa.Float(),
            nullable=False,
            server_default="50",
        ),
        sa.Column(
            "crop_zoom",
            sa.Float(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "daily_all_day",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("daily_start", sa.Time()),
        sa.Column("daily_end", sa.Time()),
        sa.Column(
            "targets_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column(
            "placement",
            sa.String(length=40),
            nullable=False,
            server_default="home",
        ),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "duration_days",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "price",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "district_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "hours_per_day",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "district_hour_rate",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "billable_district_hours",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "price_code",
            sa.String(length=80),
            nullable=False,
            server_default="",
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "views",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "clicks",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("review_state", review_state_enum, nullable=False),
        sa.Column("migration_run_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_account_id"],
            ["accounts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_business_account_id"],
            ["accounts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["migration_run_id"],
            ["migration_runs.id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_advertisements_public_schedule",
        "advertisements",
        ["placement", "status", "start_at", "end_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("advertisements")
    op.drop_table("listing_media")
    op.drop_table("listings")
    op.drop_table("catalog_items")
    op.drop_table("catalog_groups")
    op.drop_table("media_migration")
    op.drop_table("migration_issues")
    op.drop_table("legacy_id_map")
    op.drop_table("migration_runs")

    op.execute("DROP TYPE media_migration_state")
    op.execute("DROP TYPE migration_status")
    op.execute("DROP TYPE migration_stage")
    op.execute("DROP TYPE migration_environment")
    op.execute("DROP TYPE review_state")
    op.execute("DROP TYPE owner_state")
