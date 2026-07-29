from __future__ import annotations

import sqlite3

from app.legacy_migration.source import open_immutable


EXPLICIT_DEMO_FLAGS = (
    "is_demo",
    "demo",
    "is_test",
    "test_mode",
    "demo_mode",
)


def open_real_snapshot(path) -> sqlite3.Connection:
    """Open an immutable snapshot as a read-only, demo-free in-memory copy."""
    source = open_immutable(path)
    try:
        return copy_real_source(source)
    finally:
        source.close()


def copy_real_source(source: sqlite3.Connection) -> sqlite3.Connection:
    """
    Copy readable legacy tables without explicitly marked demo/test rows.

    The migration pipeline only reads this connection, therefore constraints,
    indexes, triggers and FTS shadow tables are deliberately not copied. This
    keeps every stage and verify count on the exact same real-data dataset.
    """
    target = sqlite3.connect(":memory:")
    target.row_factory = sqlite3.Row

    tables = source.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        ORDER BY name
        """
    ).fetchall()
    for record in tables:
        table = str(record["name"] if isinstance(record, sqlite3.Row) else record[0])
        if _skip_table(table):
            continue
        columns = source.execute(
            f"PRAGMA table_info({_identifier(table)})"
        ).fetchall()
        if not columns:
            continue

        column_names = [
            str(column["name"] if isinstance(column, sqlite3.Row) else column[1])
            for column in columns
        ]
        definitions = []
        for column in columns:
            name = str(column["name"] if isinstance(column, sqlite3.Row) else column[1])
            declared = str(
                column["type"] if isinstance(column, sqlite3.Row) else column[2]
            ).strip()
            definitions.append(
                f"{_identifier(name)} {declared or 'BLOB'}"
            )
        target.execute(
            f"CREATE TABLE {_identifier(table)} ({', '.join(definitions)})"
        )

        rows = source.execute(
            f"SELECT * FROM {_identifier(table)}"
        ).fetchall()
        real_rows = [row for row in rows if not _is_explicit_demo(row, column_names)]
        if not real_rows:
            continue
        placeholders = ",".join("?" for _ in column_names)
        target.executemany(
            f"INSERT INTO {_identifier(table)} VALUES ({placeholders})",
            [tuple(row[name] for name in column_names) for row in real_rows],
        )

    target.commit()
    return target


def _is_explicit_demo(row, column_names: list[str]) -> bool:
    for key in EXPLICIT_DEMO_FLAGS:
        if key in column_names and _truthy(row[key]):
            return True
    return False


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "demo",
        "test",
    }


def _skip_table(name: str) -> bool:
    normalized = name.casefold()
    return (
        normalized.startswith("sqlite_")
        or "_fts" in normalized
        or normalized.startswith("rtree_")
    )


def _identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
