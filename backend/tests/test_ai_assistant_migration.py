from pathlib import Path


def test_ai_assistant_migration_follows_specialists_and_preserves_history():
    path = Path(__file__).parents[1] / "migrations/versions/0040_ai_assistant_domain.py"
    source = path.read_text(encoding="utf-8")
    assert 'down_revision = "0039_specialists_domain"' in source
    assert '"ai_chat_messages"' in source
    assert "ai_chat_history" in source
    assert "ON CONFLICT DO NOTHING" in source
