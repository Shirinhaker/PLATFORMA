from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0008_listings_live_v1656.py"
)


def test_listing_live_migration_backfills_v7_and_payload_rows_with_media():
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "0008_listings_live_v1656"' in source
    assert 'down_revision = "0007_catalog_live_sync"' in source
    assert "cabinet_resources" in source
    assert "cabinet_records" in source
    assert "cabinet_record_fields" in source
    assert "business_profiles" in source
    assert "legacy_id_map" in source
    assert "listing_source" in source
    assert "listing_media" in source
    assert "ON CONFLICT" in source.upper()


def test_listing_live_migration_adds_saves_indexes_and_is_reversible():
    source = MIGRATION.read_text(encoding="utf-8")

    assert "source_record_key" in source
    assert "uq_listings_business_source" in source
    assert "ix_listings_public_v1656" in source
    assert "listing_saves" in source
    assert "nullable=True" in source
    assert "def downgrade()" in source
    assert "drop_table" in source
    assert "drop_column" in source


def test_listing_live_migration_backfills_legacy_saved_listings():
    source = MIGRATION.read_text(encoding="utf-8")

    assert "saved_source" in source
    assert "resource.resource = 'saved'" in source
    assert "profile.cabinet_payload::jsonb, '{}'::jsonb)->'saved'" in source
    assert "mapping.entity_type = 'listing'" in source
    assert "INSERT INTO listing_saves" in source
    assert "ON CONFLICT (owner_user_account_id, listing_id) DO NOTHING" in source


def test_listing_live_migration_removes_live_rows_before_restoring_not_null():
    source = MIGRATION.read_text(encoding="utf-8")
    downgrade = source[source.index("def downgrade() -> None:"):]

    assert "DELETE FROM listing_media WHERE migration_run_id IS NULL" in downgrade
    assert "DELETE FROM listings WHERE migration_run_id IS NULL" in downgrade
    assert downgrade.index("DELETE FROM listing_media") < downgrade.index(
        'op.alter_column("listing_media", "migration_run_id", nullable=False)'
    )
    assert downgrade.index("DELETE FROM listings") < downgrade.index(
        'op.alter_column("listings", "migration_run_id", nullable=False)'
    )
