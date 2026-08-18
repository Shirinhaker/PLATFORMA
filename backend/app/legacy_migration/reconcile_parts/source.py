"""Manba bazasidan qator o'qish."""

from __future__ import annotations

import sqlite3


def _source_rows(
    source: sqlite3.Connection,
    table: str,
) -> list[dict[str, object]]:
    cursor = source.execute(f'SELECT * FROM "{table}" ORDER BY id')
    names = [description[0] for description in cursor.description]
    return [
        {name: row[index] for index, name in enumerate(names)}
        for row in cursor.fetchall()
    ]
