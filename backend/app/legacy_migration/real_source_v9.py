from __future__ import annotations

import sqlite3
from pathlib import Path

from app.legacy_migration.real_source_v7 import copy_real_source as copy_v7
from app.legacy_migration.source import open_immutable


PRESERVE_DEMO_FLAG_TABLES = frozenset({"business_subscriptions"})


def open_real_snapshot(path: str | Path) -> sqlite3.Connection:
    """Open the identity-pruned snapshot with real entitlements intact.

    V9's staging wrapper removes demo owners and their businesses before it
    creates the immutable snapshot.  A remaining subscription row whose
    ``is_demo`` value is true therefore belongs to a real business; the flag
    describes how the plan was activated, not whether the owner is fake.
    """
    source = open_immutable(Path(path))
    try:
        return copy_real_source(source)
    finally:
        source.close()


def copy_real_source(source: sqlite3.Connection) -> sqlite3.Connection:
    return copy_v7(
        source,
        preserve_demo_flag_tables=PRESERVE_DEMO_FLAG_TABLES,
    )
