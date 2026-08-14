"""Katta oqim uchun qidiruv va outbox indekslari."""

from alembic import op


revision = "0043_operational_hardening"
down_revision = "0042_real_business_subscriptions"
branch_labels = None
depends_on = None


TRIGRAM_INDEXES = (
    ("ix_user_profiles_name_trgm", "user_profiles", "name"),
    ("ix_user_profiles_username_trgm", "user_profiles", "public_username"),
    ("ix_user_profiles_region_trgm", "user_profiles", "region"),
    ("ix_user_profiles_district_trgm", "user_profiles", "district"),
    ("ix_user_profiles_mahalla_trgm", "user_profiles", "mahalla"),
    ("ix_business_profiles_name_trgm", "business_profiles", "name"),
    ("ix_business_profiles_username_trgm", "business_profiles", "public_username"),
    ("ix_business_profiles_description_trgm", "business_profiles", "description"),
    ("ix_business_profiles_direction_trgm", "business_profiles", "direction"),
    ("ix_business_profiles_activity_trgm", "business_profiles", "activity_type"),
    ("ix_specialist_profiles_profession_trgm", "specialist_profiles", "profession"),
    ("ix_specialist_profiles_description_trgm", "specialist_profiles", "description"),
    ("ix_catalog_items_name_trgm", "catalog_items", "name"),
    ("ix_catalog_items_note_trgm", "catalog_items", "note"),
    ("ix_catalog_items_price_trgm", "catalog_items", "price_text"),
    ("ix_listings_title_trgm", "listings", "title"),
    ("ix_listings_description_trgm", "listings", "description"),
    ("ix_listings_address_trgm", "listings", "address"),
    ("ix_listings_price_trgm", "listings", "price_text"),
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for index_name, table_name, column_name in TRIGRAM_INDEXES:
        op.execute(
            f'CREATE INDEX IF NOT EXISTS "{index_name}" '
            f'ON "{table_name}" USING gin (lower("{column_name}") gin_trgm_ops)'
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_platform_outbox_claim "
        "ON platform_outbox (status, available_at, locked_at, id)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS ix_platform_outbox_claim")
    for index_name, _table_name, _column_name in reversed(TRIGRAM_INDEXES):
        op.execute(f'DROP INDEX IF EXISTS "{index_name}"')
