from pathlib import Path

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "0039_specialists_domain.py"
)


def test_specialist_migration_backfills_core_and_all_three_child_resources():
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'down_revision = "0038_documents_domain"' in source
    for table in (
        "specialist_profiles",
        "specialist_credentials",
        "specialist_offers",
        "specialist_portfolio",
    ):
        assert f'"{table}"' in source
    assert "user_profiles" in source
    assert "specialist_profile" in source
    assert "cabinet_resources" in source
    assert "cabinet_payload" in source
    assert source.count("DO NOTHING") == 4


def test_specialist_migration_is_additive_and_downgrade_only_drops_new_tables():
    source = MIGRATION.read_text(encoding="utf-8")
    downgrade = source.split("def downgrade() -> None:", 1)[1]

    for table in (
        "specialist_profiles",
        "specialist_credentials",
        "specialist_offers",
        "specialist_portfolio",
    ):
        assert f'op.drop_table("{table}")' in downgrade
    assert "user_profiles" not in downgrade
    assert "cabinet_resources" not in downgrade
