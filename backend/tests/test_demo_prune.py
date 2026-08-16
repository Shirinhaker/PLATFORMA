"""Demo yozuvlarni chiqarish — real akkauntga tegmasligi shart.

Bu funksiya migratsiya oqimidagi yagona **o'chiruvchi** qadam, shuning
uchun testlar avvalo "nima o'chmasligi kerak" ni tekshiradi.
"""

import pathlib
import sqlite3
import subprocess
import sys

import pytest

from app.legacy_migration.demo_prune import (
    DEMO_LOGIN_PREFIX,
    PruneAbort,
    prune_demo_records,
)

SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, login TEXT, tg_id INTEGER,
                    name TEXT);
CREATE TABLE businesses (id INTEGER PRIMARY KEY, user_id INTEGER,
                         biz_login TEXT, name TEXT);
CREATE TABLE listings (id INTEGER PRIMARY KEY, user_id INTEGER,
                       business_id INTEGER, title TEXT);
CREATE TABLE items (id INTEGER PRIMARY KEY, business_id INTEGER, name TEXT);
CREATE TABLE listing_media (id INTEGER PRIMARY KEY, listing_id INTEGER);
CREATE TABLE saved (id INTEGER PRIMARY KEY, user_id INTEGER,
                    listing_id INTEGER);
CREATE TABLE business_subscriptions (id INTEGER PRIMARY KEY,
                                     business_id INTEGER);
"""


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA)
    connection.executescript(
        """
        INSERT INTO users VALUES
            (1, 'user905189', 1423181561, 'bunyod'),
            (2, 'user354463', NULL, 'Muhabbat'),
            (3, 'demo_v1616_qumqorgon_01', NULL, 'Yangi non egasi'),
            (4, 'demo_v1616_qumqorgon_02', NULL, 'Sut egasi');
        INSERT INTO businesses VALUES
            (1, 1, 'biz218472', 'muhr'),
            (2, 3, NULL, 'Yangi non'),
            (3, 4, NULL, 'Sut mahsulotlari');
        INSERT INTO listings VALUES
            (1, 1, 1, 'Haqiqiy e''lon'),
            (2, 3, 2, 'Demo non'),
            (3, 2, NULL, 'Muhabbat e''loni'),
            (4, NULL, 3, 'Demo sut');
        INSERT INTO items VALUES
            (1, 1, 'Haqiqiy mahsulot'),
            (2, 2, 'Demo non mahsuloti');
        INSERT INTO listing_media VALUES (1, 1), (2, 2);
        INSERT INTO saved VALUES (1, 1, 2);
        INSERT INTO business_subscriptions VALUES (1, 1), (2, 2);
        """
    )
    connection.commit()
    return connection


def _rows(connection, table, column="id"):
    return sorted(
        row[0] for row in connection.execute(f"SELECT {column} FROM {table}")
    )


def test_real_accounts_and_their_data_survive():
    connection = _database()

    prune_demo_records(connection)

    assert _rows(connection, "users") == [1, 2]
    assert _rows(connection, "businesses") == [1]
    # 1 — biznes e'loni, 3 — oddiy foydalanuvchi e'loni.
    assert _rows(connection, "listings") == [1, 3]
    assert _rows(connection, "items") == [1]


def test_demo_accounts_and_everything_they_own_are_removed():
    connection = _database()

    removed = prune_demo_records(connection)

    assert removed["users"] == 2
    assert removed["businesses"] == 2
    assert removed["listings"] == 2
    assert removed["items"] == 1
    assert _rows(connection, "listing_media", "listing_id") == [1]
    assert _rows(connection, "business_subscriptions", "business_id") == [1]
    assert _rows(connection, "saved") == []


def test_listing_owned_by_a_demo_business_is_removed():
    """Egasi bo'sh, lekin biznesi demo bo'lgan e'lon ham ketadi."""
    connection = _database()

    prune_demo_records(connection)

    assert 4 not in _rows(connection, "listings")


def test_telegram_linked_account_aborts_the_whole_prune():
    """Prefiks real akkauntga tegsa — hech narsa o'chmaydi."""
    connection = _database()
    connection.execute(
        "UPDATE users SET tg_id = 7249897428 WHERE id = 3"
    )
    connection.commit()

    with pytest.raises(PruneAbort) as abort:
        prune_demo_records(connection)

    assert "3" in str(abort.value)
    assert _rows(connection, "users") == [1, 2, 3, 4]
    assert _rows(connection, "listings") == [1, 2, 3, 4]


def test_no_demo_records_leaves_the_database_untouched():
    connection = _database()
    connection.execute(
        "UPDATE users SET login = 'user000001' WHERE id = 3"
    )
    connection.execute(
        "UPDATE users SET login = 'user000002' WHERE id = 4"
    )
    connection.commit()

    assert prune_demo_records(connection) == {}
    assert _rows(connection, "users") == [1, 2, 3, 4]
    assert _rows(connection, "listings") == [1, 2, 3, 4]


def test_prefix_is_the_documented_one():
    assert DEMO_LOGIN_PREFIX == "demo_v1616_"


def test_module_actually_runs_as_a_command(tmp_path):
    """`python -m ...` haqiqatan ishlashi kerak.

    V8 skripti modulni shu tarzda chaqiradi. `main()` bor edi, lekin uni
    chaqiradigan `__main__` bloki yo'q edi — modul jimgina hech narsa
    qilmasdi va migratsiya demo yozuvlar bilan davom etardi.
    """
    path = tmp_path / "source.db"
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    connection.executescript(
        "INSERT INTO users VALUES "
        "(1, 'user905189', 1423181561, 'bunyod'), "
        "(2, 'demo_v1616_qumqorgon_01', NULL, 'Demo egasi');"
    )
    connection.commit()
    connection.close()

    result = subprocess.run(
        [sys.executable, "-m", "app.legacy_migration.demo_prune", str(path)],
        capture_output=True,
        text=True,
        cwd=pathlib.Path(__file__).resolve().parent.parent,
    )

    assert result.returncode == 0, result.stderr
    assert "DEMO_PRUNE_OK" in result.stdout
    assert "users=1" in result.stdout

    connection = sqlite3.connect(path)
    assert _rows(connection, "users") == [1]
    connection.close()


def test_command_aborts_without_deleting_when_a_guard_trips(tmp_path):
    path = tmp_path / "source.db"
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    connection.executescript(
        "INSERT INTO users VALUES "
        "(1, 'demo_v1616_qumqorgon_01', 7249897428, 'Telegramli');"
    )
    connection.commit()
    connection.close()

    result = subprocess.run(
        [sys.executable, "-m", "app.legacy_migration.demo_prune", str(path)],
        capture_output=True,
        text=True,
        cwd=pathlib.Path(__file__).resolve().parent.parent,
    )

    assert result.returncode != 0
    assert "demo_prune_would_drop_linked_account" in result.stderr
    connection = sqlite3.connect(path)
    assert _rows(connection, "users") == [1]
    connection.close()


def test_missing_optional_table_is_skipped():
    """Eski nusxalarda ba'zi jadval bo'lmasligi mumkin."""
    connection = _database()
    connection.execute("DROP TABLE saved")
    connection.commit()

    removed = prune_demo_records(connection)

    assert removed["users"] == 2
