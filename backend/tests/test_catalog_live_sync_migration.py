from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0007_catalog_live_sync.py"
)


def test_catalog_live_sync_migration_has_schema_identity_and_backfill():
    assert MIGRATION.exists()
    source = MIGRATION.read_text()

    assert 'revision = "0007_catalog_live_sync"' in source
    assert 'down_revision = "0006_v7_cabinet_records"' in source
    assert "source_record_key" in source
    assert "ix_catalog_groups_live_source" in source
    assert "ix_catalog_items_live_source" in source
    assert "ix_catalog_items_catalog_group_id" in source
    assert "cabinet_resources" in source
    assert "cabinet_records" in source
    assert "cabinet_record_fields" in source
    assert "business_profiles" in source
    assert "catalog_groups" in source
    assert "catalog_items" in source
    assert "ON CONFLICT" in source.upper()


def test_catalog_live_sync_migration_keeps_legacy_rows_and_is_reversible():
    source = MIGRATION.read_text()

    assert "migration_run_id" in source
    assert "nullable=True" in source
    assert "def downgrade()" in source
    assert "drop_index" in source
    assert "drop_column" in source
