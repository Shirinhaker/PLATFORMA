"""Public search uchun pg_trgm indekslari.

Revision ID: 0043_public_search_trgm
Revises: 0042_real_business_subscriptions
"""

from alembic import op


revision = "0043_public_search_trgm"
down_revision = "0042_real_business_subscriptions"
branch_labels = None
depends_on = None


INDEXES = {
    "ix_user_profiles_name_trgm": ("user_profiles", "name"),
    "ix_user_profiles_username_trgm": ("user_profiles", "public_username"),
    "ix_user_profiles_region_trgm": ("user_profiles", "region"),
    "ix_user_profiles_district_trgm": ("user_profiles", "district"),
    "ix_user_profiles_mahalla_trgm": ("user_profiles", "mahalla"),
    "ix_business_profiles_name_trgm": ("business_profiles", "name"),
    "ix_business_profiles_username_trgm": ("business_profiles", "public_username"),
    "ix_business_profiles_description_trgm": ("business_profiles", "description"),
    "ix_business_profiles_direction_trgm": ("business_profiles", "direction"),
    "ix_business_profiles_activity_trgm": ("business_profiles", "activity_type"),
    "ix_specialist_profiles_profession_trgm": ("specialist_profiles", "profession"),
    "ix_specialist_profiles_description_trgm": ("specialist_profiles", "description"),
    "ix_catalog_items_name_trgm": ("catalog_items", "name"),
    "ix_catalog_items_note_trgm": ("catalog_items", "note"),
    "ix_listings_title_trgm": ("listings", "title"),
    "ix_listings_description_trgm": ("listings", "description"),
    "ix_listings_address_trgm": ("listings", "address"),
}


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    with op.get_context().autocommit_block():
        for name, (table, column) in INDEXES.items():
            op.execute(
                f'CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON {table} '
                f'USING gin (lower("{column}") gin_trgm_ops)'
            )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name in reversed(INDEXES):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
