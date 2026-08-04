"""Public ID qidiruvlarini O(N) skandan indekslangan qidiruvga o'tkazish.

Revision ID: 0010_public_id_indexed_lookup
Revises: 0009_orders_live_v1656
"""

import hashlib
from collections.abc import Callable

from alembic import context, op
import sqlalchemy as sa


revision = "0010_public_id_indexed_lookup"
down_revision = "0009_orders_live_v1656"
branch_labels = None
depends_on = None


def _profile_public_id(kind: str, target_id: int) -> str:
    digest = hashlib.blake2s(
        f"{kind}:{target_id}".encode("utf-8"),
        digest_size=8,
        person=b"koprik",
    ).hexdigest()
    return f"{'u' if kind == 'user' else 'b'}_{digest}"


def _content_public_id(kind: str, target_id: int) -> str:
    digest = hashlib.blake2s(
        f"{kind}:{target_id}".encode("utf-8"),
        digest_size=8,
        key=b"koprik-content-v1",
    ).hexdigest()
    return f"{'p' if kind == 'product' else 's'}_{digest}"


def _listing_public_id(_kind: str, target_id: int) -> str:
    digest = hashlib.blake2s(
        f"listing:{target_id}".encode("utf-8"),
        digest_size=8,
        key=b"koprik-content-v1",
    ).hexdigest()
    return f"l_{digest}"


def _backfill_public_ids(
    table: str,
    id_column: str,
    *,
    kind: str = "",
    kind_column: str | None = None,
    builder: Callable[[str, int], str],
    batch_size=1000,
) -> None:
    if context.is_offline_mode():
        # `--sql` rejimida bazadan o'qib bo'lmaydi (blake2s ni PostgreSQL
        # hisoblab bera olmaydi). Backfill jonli ulanishda bajariladi.
        op.execute(
            f"-- {table}.public_id backfill jonli ulanishda bajariladi"
        )
        return
    connection = op.get_bind()
    last_id = 0
    kind_select = f", {kind_column} AS target_kind" if kind_column else ""
    while True:
        rows = connection.execute(
            sa.text(
                f"""
                SELECT {id_column} AS target_id{kind_select}
                FROM {table}
                WHERE {id_column} > :last_id
                  AND public_id IS NULL
                ORDER BY {id_column}
                LIMIT :batch_size
                """
            ),
            {"last_id": last_id, "batch_size": batch_size},
        ).mappings().all()
        if not rows:
            return
        updates = [
            {
                "target_id": int(row["target_id"]),
                "public_id": builder(
                    str(row["target_kind"]) if kind_column else kind,
                    int(row["target_id"]),
                ),
            }
            for row in rows
        ]
        connection.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET public_id = :public_id
                WHERE {id_column} = :target_id
                  AND public_id IS NULL
                """
            ),
            updates,
        )
        last_id = int(rows[-1]["target_id"])


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("public_id", sa.String(length=18), nullable=True),
    )
    op.add_column(
        "business_profiles",
        sa.Column("public_id", sa.String(length=18), nullable=True),
    )
    op.add_column(
        "catalog_items",
        sa.Column("public_id", sa.String(length=18), nullable=True),
    )
    op.add_column(
        "listings",
        sa.Column("public_id", sa.String(length=18), nullable=True),
    )

    _backfill_public_ids(
        "user_profiles",
        "account_id",
        kind="user",
        builder=_profile_public_id,
    )
    _backfill_public_ids(
        "business_profiles",
        "account_id",
        kind="business",
        builder=_profile_public_id,
    )
    _backfill_public_ids(
        "catalog_items",
        "id",
        kind_column="kind",
        builder=_content_public_id,
    )
    _backfill_public_ids(
        "listings",
        "id",
        builder=_listing_public_id,
    )

    # Jadval yozuvlarini uzoq vaqt bloklamaslik uchun indekslar concurrently quriladi.
    with op.get_context().autocommit_block():
        op.create_index(
            "uq_user_profiles_public_id",
            "user_profiles",
            ["public_id"],
            unique=True,
            postgresql_concurrently=True,
        )
        op.create_index(
            "uq_business_profiles_public_id",
            "business_profiles",
            ["public_id"],
            unique=True,
            postgresql_concurrently=True,
        )
        op.create_index(
            "uq_catalog_items_public_id",
            "catalog_items",
            ["public_id"],
            unique=True,
            postgresql_concurrently=True,
        )
        op.create_index(
            "uq_listings_public_id",
            "listings",
            ["public_id"],
            unique=True,
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "uq_listings_public_id",
            table_name="listings",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "uq_catalog_items_public_id",
            table_name="catalog_items",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "uq_business_profiles_public_id",
            table_name="business_profiles",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "uq_user_profiles_public_id",
            table_name="user_profiles",
            postgresql_concurrently=True,
        )

    for table in (
        "listings",
        "catalog_items",
        "business_profiles",
        "user_profiles",
    ):
        op.drop_column(table, "public_id")
