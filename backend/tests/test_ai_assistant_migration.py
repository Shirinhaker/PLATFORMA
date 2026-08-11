from pathlib import Path


def test_ai_assistant_migration_follows_specialists_without_reading_sqlite_from_postgres():
    path = Path(__file__).parents[1] / "migrations/versions/0040_ai_assistant_domain.py"
    source = path.read_text(encoding="utf-8")
    assert 'down_revision = "0039_specialists_domain"' in source
    assert '"ai_chat_messages"' in source
    assert "FROM ai_chat_history" not in source


def test_complete_cabinet_migration_runs_the_typed_ai_history_import():
    root = Path(__file__).parents[1] / "app"
    profile_source = (root / "legacy_migration/profile_parity_v7.py").read_text(
        encoding="utf-8",
    )
    runner_source = (root / "legacy_migration/runner_v6.py").read_text(
        encoding="utf-8",
    )
    assert "import_ai_chat_history" in profile_source
    assert 'MIGRATION_SCHEMA_VERSION = "0008_phase3c_taxi_v1"' in runner_source
