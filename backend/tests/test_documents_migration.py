from pathlib import Path

MIGRATION = (
    Path(__file__).parents[1] / "migrations" / "versions" / "0038_documents_domain.py"
)


def test_documents_migration_is_additive_and_backfills_all_legacy_aliases():
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'down_revision = "0037_inventory_live_completion"' in source
    assert '"document_counterparties"' in source
    assert '"business_documents"' in source
    for resource in (
        "contractors",
        "counterparties",
        "documents",
        "business_documents",
        "incoming_documents",
        "outgoing_documents",
        "internal_documents",
    ):
        assert f'"{resource}"' in source

    assert "cabinet_resources" in source
    assert "cabinet_payload" in source
    assert "legacy_id_map" in source
    assert source.count("DO NOTHING") == 2
    assert "LINK_INCOMING_SQL" in source


def test_documents_migration_downgrade_only_removes_new_typed_tables():
    source = MIGRATION.read_text(encoding="utf-8")
    downgrade = source.split("def downgrade() -> None:", 1)[1]

    assert 'op.drop_table("business_documents")' in downgrade
    assert 'op.drop_table("document_counterparties")' in downgrade
    assert "business_profiles" not in downgrade.replace(
        'op.drop_index("ix_business_profiles_tax_id_documents", '
        'table_name="business_profiles")',
        "",
    )
    assert "cabinet_resources" not in downgrade
