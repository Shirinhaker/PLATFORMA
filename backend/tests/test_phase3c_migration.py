from pathlib import Path


MIGRATION = Path("migrations/versions/0003_phase3c_content.py")


def test_phase3c_migration_declares_all_tables_and_parent():
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "0003_phase3c_content"' in source
    assert 'down_revision = "0002_auth_profiles"' in source
    for table in (
        "migration_runs",
        "legacy_id_map",
        "migration_issues",
        "media_migration",
        "catalog_groups",
        "catalog_items",
        "listings",
        "listing_media",
        "advertisements",
    ):
        assert f'op.create_table(\n        "{table}"' in source


def test_phase3c_migration_has_idempotency_and_public_indexes():
    source = MIGRATION.read_text(encoding="utf-8")

    assert "uq_legacy_id_map" in source
    assert "uq_media_migration_source_slot" in source
    assert "ix_catalog_items_public" in source
    assert "ix_advertisements_public_schedule" in source


def test_phase3c_migration_downgrade_is_reverse_dependency_order():
    source = MIGRATION.read_text(encoding="utf-8")
    downgrade = source.split("def downgrade() -> None:", maxsplit=1)[1]
    tables = [
        "advertisements",
        "listing_media",
        "listings",
        "catalog_items",
        "catalog_groups",
        "media_migration",
        "migration_issues",
        "legacy_id_map",
        "migration_runs",
    ]

    positions = [downgrade.index(f'op.drop_table("{table}")') for table in tables]
    assert positions == sorted(positions)
