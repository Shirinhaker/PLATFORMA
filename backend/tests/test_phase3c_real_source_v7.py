import sqlite3

from app.legacy_migration.real_source_v7 import copy_real_source


def source_database() -> sqlite3.Connection:
    source = sqlite3.connect(":memory:")
    source.row_factory = sqlite3.Row
    source.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            is_demo INTEGER DEFAULT 0
        );
        CREATE TABLE listings (
            id INTEGER PRIMARY KEY,
            title TEXT,
            demo_mode TEXT DEFAULT ''
        );
        CREATE TABLE advertisements (
            id INTEGER PRIMARY KEY,
            title TEXT,
            is_test INTEGER DEFAULT 0
        );
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            title TEXT,
            body TEXT
        );
        CREATE VIRTUAL TABLE users_fts USING fts5(name);
        """
    )
    source.executemany(
        "INSERT INTO users VALUES (?,?,?)",
        [
            (1, "Haqiqiy", 0),
            (2, "Demo", 1),
        ],
    )
    source.executemany(
        "INSERT INTO listings VALUES (?,?,?)",
        [
            (1, "Haqiqiy e’lon", ""),
            (2, "Demo e’lon", "demo"),
        ],
    )
    source.executemany(
        "INSERT INTO advertisements VALUES (?,?,?)",
        [
            (1, "Haqiqiy reklama", 0),
            (2, "Test reklama", 1),
        ],
    )
    source.execute(
        "INSERT INTO documents VALUES (1,'Shartnoma','Haqiqiy hujjat matni')"
    )
    source.commit()
    return source


def test_copy_real_source_keeps_real_rows_and_document_content():
    source = source_database()
    try:
        target = copy_real_source(source)
    finally:
        source.close()
    try:
        assert [row["name"] for row in target.execute("SELECT * FROM users")] == [
            "Haqiqiy"
        ]
        assert [row["title"] for row in target.execute("SELECT * FROM listings")] == [
            "Haqiqiy e’lon"
        ]
        assert [
            row["title"]
            for row in target.execute("SELECT * FROM advertisements")
        ] == ["Haqiqiy reklama"]
        document = target.execute("SELECT * FROM documents").fetchone()
        assert document["body"] == "Haqiqiy hujjat matni"
        assert target.execute(
            "SELECT 1 FROM sqlite_master WHERE name='users_fts'"
        ).fetchone() is None
    finally:
        target.close()


def test_copy_real_source_is_readable_by_inventory_style_queries():
    source = source_database()
    try:
        target = copy_real_source(source)
    finally:
        source.close()
    try:
        assert target.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        assert target.execute("SELECT COUNT(*) FROM listings").fetchone()[0] == 1
        assert target.execute("SELECT COUNT(*) FROM advertisements").fetchone()[0] == 1
    finally:
        target.close()
