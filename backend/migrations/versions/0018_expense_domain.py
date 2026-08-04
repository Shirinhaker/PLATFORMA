"""Xarajatlar va Ombor kirimi bog'lanishini ko'chirish.

Revision ID: 0018_expense_domain
Revises: 0017_debt_ledger_domain
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_expense_domain"
down_revision = "0017_debt_ledger_domain"
branch_labels = None
depends_on = None


JSON_VALUE_SQL = r"""
CASE field.value_type
    WHEN 'null' THEN 'null'::jsonb
    WHEN 'boolean' THEN to_jsonb(field.value_boolean)
    WHEN 'integer' THEN to_jsonb(field.value_integer)
    WHEN 'float' THEN to_jsonb(field.value_float)
    ELSE to_jsonb(COALESCE(field.value_text, ''))
END
"""


def _source_ctes(resource_name: str) -> str:
    return rf"""WITH
relational_rows AS (
    SELECT
        resource.account_id,
        record.source_key,
        record.ordinal,
        COALESCE(
            jsonb_object_agg(substr(field.path, 2), {JSON_VALUE_SQL})
                FILTER (WHERE field.path ~ '^/[^/]+$'),
            '{{}}'::jsonb
        ) AS row_data,
        0 AS priority
    FROM cabinet_resources AS resource
    JOIN cabinet_records AS record ON record.resource_id = resource.id
    LEFT JOIN cabinet_record_fields AS field ON field.record_id = record.id
    WHERE resource.account_type = 'business'
      AND resource.resource = '{resource_name}'
    GROUP BY resource.account_id, record.id, record.source_key, record.ordinal
),
payload_rows AS (
    SELECT
        profile.account_id,
        COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality)
            AS source_key,
        entry.ordinality::integer AS ordinal,
        entry.row_data,
        1 AS priority
    FROM business_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(
            COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
            -> '{resource_name}'
        ) = 'array'
        THEN COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
            -> '{resource_name}'
        ELSE '[]'::jsonb END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
),
source_rows AS (
    SELECT DISTINCT ON (account_id, source_key)
        account_id, source_key, ordinal, row_data
    FROM (
        SELECT * FROM relational_rows
        UNION ALL
        SELECT * FROM payload_rows
    ) AS candidates
    ORDER BY account_id, source_key, priority, ordinal
)
"""


CATEGORY_BACKFILL_SQL = _source_ctes("expense_cats") + r"""
INSERT INTO expense_categories (
    business_account_id, legacy_source_id, name, created_at
)
SELECT
    source.account_id,
    CASE WHEN COALESCE(source.row_data->>'id', source.source_key, '') ~ '^[0-9]+$'
        THEN COALESCE(source.row_data->>'id', source.source_key)::bigint
        ELSE NULL END,
    left(trim(source.row_data->>'name'), 40),
    CASE WHEN COALESCE(source.row_data->>'created_at', '')
        ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((source.row_data->>'created_at')::double precision)
        ELSE now() END
FROM source_rows AS source
WHERE length(trim(COALESCE(source.row_data->>'name', ''))) > 0
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO UPDATE SET name = EXCLUDED.name
"""


EXPENSE_BACKFILL_SQL = _source_ctes("expenses") + r"""
INSERT INTO expenses (
    business_account_id, legacy_source_id, category, amount, note, source,
    inventory_stock_move_id, performed_by_staff_id, actor_name_snapshot,
    created_at
)
SELECT
    source.account_id,
    CASE WHEN COALESCE(source.row_data->>'id', source.source_key, '') ~ '^[0-9]+$'
        THEN COALESCE(source.row_data->>'id', source.source_key)::bigint
        ELSE NULL END,
    left(COALESCE(NULLIF(trim(source.row_data->>'category'), ''), 'Boshqa'), 40),
    (source.row_data->>'amount')::bigint,
    left(COALESCE(source.row_data->>'note', ''), 200),
    left(COALESCE(NULLIF(source.row_data->>'source', ''), 'manual'), 32),
    move.id,
    NULL::bigint,
    '',
    CASE WHEN COALESCE(source.row_data->>'created_at', '')
        ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((source.row_data->>'created_at')::double precision)
        ELSE now() END
FROM source_rows AS source
LEFT JOIN inventory_stock_moves AS move
  ON move.business_account_id = source.account_id
 AND move.legacy_source_id = CASE
    WHEN COALESCE(source.row_data->>'stock_move_id', '') ~ '^[0-9]+$'
    THEN (source.row_data->>'stock_move_id')::bigint ELSE NULL END
WHERE COALESCE(source.row_data->>'amount', '') ~ '^[0-9]+$'
  AND (source.row_data->>'amount')::bigint > 0
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO UPDATE SET
    category = EXCLUDED.category,
    amount = EXCLUDED.amount,
    note = EXCLUDED.note,
    source = EXCLUDED.source,
    inventory_stock_move_id = EXCLUDED.inventory_stock_move_id
"""


def upgrade() -> None:
    op.create_table(
        "expense_categories",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_expense_categories_name_required",
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_expense_categories_business",
        "expense_categories",
        ["business_account_id", "created_at", "id"],
    )
    op.create_index(
        "uq_expense_categories_business_legacy",
        "expense_categories",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "uq_expense_categories_business_name",
        "expense_categories",
        ["business_account_id", "name"],
        unique=True,
    )
    op.create_table(
        "expenses",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "source", sa.String(length=32), nullable=False, server_default="manual"
        ),
        sa.Column("inventory_stock_move_id", sa.BigInteger()),
        sa.Column("performed_by_staff_id", sa.BigInteger()),
        sa.Column(
            "actor_name_snapshot",
            sa.String(length=160),
            nullable=False,
            server_default="",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        sa.CheckConstraint(
            "length(trim(category)) > 0",
            name="ck_expenses_category_required",
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["inventory_stock_move_id"],
            ["inventory_stock_moves.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["performed_by_staff_id"], ["staff_members.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_expenses_business_created",
        "expenses",
        ["business_account_id", "created_at", "id"],
    )
    op.create_index(
        "uq_expenses_business_legacy",
        "expenses",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "uq_expenses_stock_move",
        "expenses",
        ["inventory_stock_move_id"],
        unique=True,
        postgresql_where=sa.text("inventory_stock_move_id IS NOT NULL"),
    )

    op.execute(CATEGORY_BACKFILL_SQL)
    op.execute(EXPENSE_BACKFILL_SQL)


def downgrade() -> None:
    op.drop_index("uq_expenses_stock_move", table_name="expenses")
    op.drop_index("uq_expenses_business_legacy", table_name="expenses")
    op.drop_index("ix_expenses_business_created", table_name="expenses")
    op.drop_table("expenses")
    op.drop_index(
        "uq_expense_categories_business_name", table_name="expense_categories"
    )
    op.drop_index(
        "uq_expense_categories_business_legacy", table_name="expense_categories"
    )
    op.drop_index(
        "ix_expense_categories_business", table_name="expense_categories"
    )
    op.drop_table("expense_categories")
