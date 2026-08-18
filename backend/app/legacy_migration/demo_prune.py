"""v1616 demo yozuvlarini migratsiya doirasidan chiqaradi.

v1656 bazasida namoyish uchun yaratilgan 20 ta akkaunt va ularning
bizneslari, e'lonlari va mahsulotlari bor. Ular yangi platformaga
ko'chirilmasligi kerak — aks holda ochilish kuni bosh sahifada soxta
e'lonlar turadi.

Tozalash **v1656 ga tegmaydi**: V8 oqimi arxivni vaqtinchalik papkaga
chiqaradi va bu funksiya o'sha nusxada ishlaydi. Snapshot shundan keyin
olinadi, shuning uchun barmoq izi va gate sanoqlari o'z-o'zidan mos
bo'ladi.

Demo belgisi — login prefiksi. Prefiks noto'g'ri bo'lsa real akkaunt
o'chib ketmasligi uchun `PruneAbort` qo'riqchisi bor: Telegram raqami
bog'langan akkaunt hech qachon demo deb hisoblanmaydi.
"""

from __future__ import annotations

import sqlite3

DEMO_LOGIN_PREFIX = "demo_v1616_"

#: (jadval, ustun) — o'chirish tartibi bolalardan ota-onaga qarab.
_DELETE_ORDER = (
    ("listing_media", "listing_id", "listings"),
    ("saved", "listing_id", "listings"),
    ("listings", "id", "listings"),
    ("items", "id", "items"),
    ("business_subscriptions", "business_id", "businesses"),
    ("businesses", "id", "businesses"),
    ("users", "id", "users"),
)


class PruneAbort(RuntimeError):
    """Prefiks real akkauntga tegib ketgan — hech narsa o'chirilmaydi."""


def _ids(cursor: sqlite3.Cursor, sql: str, *params: object) -> list[int]:
    return [int(row[0]) for row in cursor.execute(sql, params)]


def _joined(values: list[int]) -> str:
    return ",".join(str(value) for value in values)


def _table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    return bool(
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
    )


def prune_demo_records(
    connection: sqlite3.Connection,
    *,
    login_prefix: str = DEMO_LOGIN_PREFIX,
) -> dict[str, int]:
    """Demo akkauntlar va ularga tegishli hamma narsani o'chiradi.

    Nechta qator o'chirilgani jadval bo'yicha qaytariladi. Demo topilmasa
    bo'sh lug'at qaytadi va baza o'zgarmaydi.
    """
    connection.execute("PRAGMA foreign_keys = OFF")
    cursor = connection.cursor()

    users = _ids(cursor, "SELECT id FROM users WHERE login LIKE ? || '%'", login_prefix)
    if not users:
        return {}

    linked = _ids(
        cursor,
        f"SELECT id FROM users WHERE id IN ({_joined(users)}) AND tg_id IS NOT NULL",
    )
    if linked:
        raise PruneAbort("demo_prune_would_drop_linked_account:" + _joined(linked))

    businesses = _ids(
        cursor,
        f"SELECT id FROM businesses WHERE user_id IN ({_joined(users)})",
    )
    owner_filter = f"user_id IN ({_joined(users)})"
    if businesses:
        owner_filter += f" OR business_id IN ({_joined(businesses)})"
    listings = _ids(cursor, "SELECT id FROM listings WHERE " + owner_filter)
    items = (
        _ids(
            cursor,
            f"SELECT id FROM items WHERE business_id IN ({_joined(businesses)})",
        )
        if businesses
        else []
    )

    groups = {
        "listings": listings,
        "items": items,
        "businesses": businesses,
        "users": users,
    }
    removed: dict[str, int] = {}
    for table, column, group in _DELETE_ORDER:
        values = groups[group]
        if not values or not _table_exists(cursor, table):
            continue
        cursor.execute(f'DELETE FROM "{table}" WHERE "{column}" IN ({_joined(values)})')
        if cursor.rowcount:
            removed[table] = cursor.rowcount
    connection.commit()
    return removed


def main() -> None:
    import sys

    connection = sqlite3.connect(sys.argv[1])
    try:
        removed = prune_demo_records(connection)
    except PruneAbort as abort:
        raise SystemExit(f"PHASE3C_V8_ERROR={abort}") from abort
    finally:
        connection.close()
    if not removed:
        print("DEMO_PRUNE_SKIPPED reason=no_match")
        return
    print(
        "DEMO_PRUNE_OK "
        + " ".join(f"{table}={count}" for table, count in sorted(removed.items()))
    )


if __name__ == "__main__":
    main()
