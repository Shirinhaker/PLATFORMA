import sqlite3
from types import SimpleNamespace

import pytest

from app.ai_assistant.legacy_import import import_ai_chat_history
from app.ai_assistant.model import AIChatMessage
from app.legacy_migration.model import LegacyIdMap


class ScalarResult:
    def __init__(self, value):
        self._value = value

    def one_or_none(self):
        return self._value


class FakeSession:
    def __init__(self):
        self.added = []
        self._message_lookup = 0

    async def scalars(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity is LegacyIdMap:
            return ScalarResult(SimpleNamespace(target_id=17))
        assert entity is AIChatMessage
        index = self._message_lookup
        self._message_lookup += 1
        existing = self.added[index - 2] if index >= 2 else None
        return ScalarResult(existing)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None


def legacy_source():
    source = sqlite3.connect(":memory:")
    source.row_factory = sqlite3.Row
    source.execute(
        """
        CREATE TABLE ai_chat_history(
            id INTEGER PRIMARY KEY,
            business_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
        """
    )
    source.executemany(
        "INSERT INTO ai_chat_history VALUES(?,?,?,?,?,?)",
        (
            (1, 7, 3, "user", "Bugun qanday?", 1_723_283_200),
            (2, 7, 3, "assistant", "Bugun yaxshi.", 1_723_283_201),
            (3, 7, 3, "system", "ko'chmasin", 1_723_283_202),
        ),
    )
    return source


@pytest.mark.asyncio
async def test_legacy_ai_history_uses_business_mapping_and_is_idempotent():
    source = legacy_source()
    session = FakeSession()
    run = SimpleNamespace(id=9)
    try:
        first = await import_ai_chat_history(session, source, run)
        second = await import_ai_chat_history(session, source, run)
    finally:
        source.close()

    assert first.created == 2
    assert second.reused == 2
    assert len(session.added) == 2
    assert [row.business_account_id for row in session.added] == [17, 17]
    assert [row.legacy_source_id for row in session.added] == [1, 2]
    assert [row.source for row in session.added] == ["legacy", "legacy"]
    assert all(row.created_at.tzinfo is not None for row in session.added)
