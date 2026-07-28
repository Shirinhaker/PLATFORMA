import json
from pathlib import Path
import sqlite3

import pytest

from app.legacy_migration.source import (
    LegacySchemaMismatch,
    create_snapshot,
    inventory_source,
    open_immutable,
)


REQUIRED_TABLES = (
    "users",
    "businesses",
    "item_groups",
    "items",
    "listings",
    "listing_media",
    "advertisements",
)


def build_legacy_fixture(path: Path) -> Path:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            login TEXT,
            role TEXT,
            status TEXT
        );
        CREATE TABLE businesses (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            name TEXT,
            status TEXT
        );
        CREATE TABLE item_groups (
            id INTEGER PRIMARY KEY,
            business_id INTEGER,
            name TEXT,
            kind TEXT,
            status TEXT
        );
        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            business_id INTEGER,
            group_id INTEGER,
            name TEXT,
            kind TEXT,
            status TEXT
        );
        CREATE TABLE listings (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            title TEXT,
            status TEXT
        );
        CREATE TABLE listing_media (
            id INTEGER PRIMARY KEY,
            listing_id INTEGER,
            mtype TEXT
        );
        CREATE TABLE advertisements (
            id INTEGER PRIMARY KEY,
            title TEXT,
            status TEXT
        );
        """
    )
    connection.executemany(
        "INSERT INTO items(id, name, kind, status) VALUES (?, ?, ?, ?)",
        (
            (1, "Mebel", "product", "active"),
            (2, "Ta’mirlash", "service", "blocked"),
        ),
    )
    connection.execute(
        "INSERT INTO advertisements(id, title, status) VALUES (1, ?, ?)",
        ("Turon Savdo", "active"),
    )
    connection.execute(
        "INSERT INTO listing_media(id, listing_id, mtype) VALUES (1, 1, ?)",
        ("photo",),
    )
    connection.commit()
    connection.close()
    return path


def test_snapshot_is_consistent_read_only_and_fingerprinted(tmp_path):
    source = build_legacy_fixture(tmp_path / "platforma.db")
    result = create_snapshot(source, tmp_path / "snapshot", ())

    assert result.path.exists()
    assert len(result.database_sha256) == 64
    assert len(result.manifest_sha256) == 64
    connection = open_immutable(result.path)
    assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    with pytest.raises(sqlite3.OperationalError):
        connection.execute("INSERT INTO users(login) VALUES ('blocked')")
    connection.close()


def test_snapshot_manifest_contains_only_safe_relative_media_metadata(tmp_path):
    source = build_legacy_fixture(tmp_path / "platforma.db")
    uploads = tmp_path / "uploads"
    nested = uploads / "catalog"
    nested.mkdir(parents=True)
    (nested / "item.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBP")

    result = create_snapshot(source, tmp_path / "snapshot", (uploads,))
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert manifest == [
        {
            "reference": "root_0/catalog/item.webp",
            "sha256": (
                "44e65465e5e82733c8e5499cdd2fb106b8b703ea3f28da3b7da7f3"
                "a661267d6e"
            ),
            "size_bytes": 12,
        }
    ]
    assert str(tmp_path) not in result.manifest_path.read_text(encoding="utf-8")


def test_inventory_counts_entities_statuses_kinds_and_media_types(tmp_path):
    source = build_legacy_fixture(tmp_path / "platforma.db")
    result = create_snapshot(source, tmp_path / "snapshot", ())
    connection = open_immutable(result.path)

    inventory = inventory_source(connection)

    assert inventory["items"]["total"] == 2
    assert inventory["items"]["product"] == 1
    assert inventory["items"]["service"] == 1
    assert inventory["items"]["active"] == 1
    assert inventory["items"]["blocked"] == 1
    assert inventory["advertisements"]["active"] == 1
    assert inventory["listing_media"]["photo"] == 1
    connection.close()


def test_inventory_rejects_a_snapshot_missing_a_required_table(tmp_path):
    source = build_legacy_fixture(tmp_path / "platforma.db")
    connection = sqlite3.connect(source)
    connection.execute("DROP TABLE listings")
    connection.commit()
    connection.close()
    result = create_snapshot(source, tmp_path / "snapshot", ())
    immutable = open_immutable(result.path)

    with pytest.raises(LegacySchemaMismatch, match="listings"):
        inventory_source(immutable)
    immutable.close()
