"""Kassa, chek va Buyurtma -> Kassa -> Ombor bog‘lanishini ko‘chirish.

Revision ID: 0016_cash_register_domain
Revises: 0015_inventory_domain
"""

from alembic import op
import sqlalchemy as sa


revision = "0016_cash_register_domain"
down_revision = "0015_inventory_domain"
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


def _relational_rows() -> str:
    return rf"""
relational_rows AS (
    SELECT
        resource.account_id,
        resource.resource,
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
      AND resource.resource IN (
          'sales', 'cash_transactions', 'cash_register_transactions'
      )
    GROUP BY resource.account_id, resource.resource, record.id,
             record.source_key, record.ordinal
)
"""


def _payload_rows() -> str:
    return r"""
payload_rows AS (
    SELECT
        profile.account_id,
        resource_name.resource,
        COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality)
            AS source_key,
        entry.ordinality::integer AS ordinal,
        entry.row_data,
        1 AS priority
    FROM business_profiles AS profile
    CROSS JOIN LATERAL (
        VALUES ('sales'), ('cash_transactions'), ('cash_register_transactions')
    ) AS resource_name(resource)
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(
            COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)
            -> resource_name.resource
        ) = 'array'
        THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)
            -> resource_name.resource
        ELSE '[]'::jsonb END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
)
"""


SOURCE_CTES = (
    "WITH\n"
    + _relational_rows().strip()
    + ",\n"
    + _payload_rows().strip()
    + r""",
deduplicated AS (
    SELECT DISTINCT ON (account_id, resource, source_key)
        account_id, resource, source_key, ordinal, row_data
    FROM (
        SELECT * FROM relational_rows
        UNION ALL
        SELECT * FROM payload_rows
    ) AS candidates
    ORDER BY account_id, resource, source_key, priority, ordinal
),
source_rows AS (
    SELECT row.*,
        CASE
            WHEN row.resource = 'sales'
             AND COALESCE(row.row_data->>'source', 'manual') = 'order'
             AND COALESCE(row.row_data->>'order_id', '') ~ '^[0-9]+$'
                THEN 'sales:order:' || (row.row_data->>'order_id')
            WHEN row.resource = 'sales'
             AND COALESCE(row.row_data->>'chek_no', '') ~ '^[0-9]+$'
                THEN 'sales:chek:' || (row.row_data->>'chek_no')
            ELSE row.resource || ':row:' || row.source_key
        END AS group_key
    FROM deduplicated AS row
    WHERE row.resource = 'sales'
       OR NOT EXISTS (
            SELECT 1 FROM deduplicated AS primary_rows
            WHERE primary_rows.account_id = row.account_id
              AND primary_rows.resource = 'sales'
       )
)
"""
)


RECEIPT_BACKFILL_SQL = SOURCE_CTES + r"""
, receipt_sources AS (
    SELECT DISTINCT ON (account_id, group_key)
        source.account_id,
        source.group_key,
        source.row_data,
        source.resource,
        source.ordinal
    FROM source_rows AS source
    ORDER BY source.account_id, source.group_key, source.ordinal
)
INSERT INTO cash_receipts (
    business_account_id, receipt_no, source, order_id,
    legacy_order_source_id, legacy_group_key, pay_type,
    debtor_name_snapshot, legacy_debtor_source_id, note,
    created_by_staff_id, actor_name_snapshot, created_at
)
SELECT
    source.account_id,
    CASE WHEN source.resource = 'sales'
          AND COALESCE(source.row_data->>'chek_no', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'chek_no')::bigint ELSE NULL END,
    CASE
        WHEN source.resource = 'sales'
         AND source.row_data->>'source' IN ('order','dining','education')
            THEN source.row_data->>'source'
        WHEN source.resource = 'sales'
         AND source.row_data->>'source' = 'qarzpay' THEN 'debt_payment'
        ELSE 'manual'
    END,
    target_order.id,
    CASE WHEN COALESCE(source.row_data->>'order_id', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'order_id')::bigint ELSE NULL END,
    source.group_key,
    CASE WHEN source.row_data->>'pay_type' IN ('naqd','karta','qarz')
        THEN source.row_data->>'pay_type' ELSE '' END,
    left(COALESCE(
        source.row_data->>'debtor_name', source.row_data->>'customer_name', ''
    ), 160),
    CASE WHEN COALESCE(source.row_data->>'debtor_id', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'debtor_id')::bigint ELSE NULL END,
    left(COALESCE(
        source.row_data->>'note', source.row_data->>'description', ''
    ), 200),
    NULL::bigint,
    left(COALESCE(source.row_data->>'who', ''), 160),
    CASE WHEN COALESCE(source.row_data->>'created_at', '')
        ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((source.row_data->>'created_at')::double precision)
        ELSE now() END
FROM receipt_sources AS source
LEFT JOIN orders AS target_order
  ON target_order.provider_account_id = source.account_id
 AND target_order.legacy_source_id = CASE
    WHEN COALESCE(source.row_data->>'order_id', '') ~ '^[0-9]+$'
    THEN (source.row_data->>'order_id')::bigint ELSE NULL END
ON CONFLICT (business_account_id, legacy_group_key)
    WHERE legacy_group_key IS NOT NULL
DO UPDATE SET
    order_id = COALESCE(EXCLUDED.order_id, cash_receipts.order_id),
    legacy_order_source_id = EXCLUDED.legacy_order_source_id,
    pay_type = EXCLUDED.pay_type,
    debtor_name_snapshot = EXCLUDED.debtor_name_snapshot,
    legacy_debtor_source_id = EXCLUDED.legacy_debtor_source_id,
    note = EXCLUDED.note,
    actor_name_snapshot = EXCLUDED.actor_name_snapshot
"""


LINE_BACKFILL_SQL = SOURCE_CTES + r"""
INSERT INTO cash_receipt_lines (
    receipt_id, business_account_id, catalog_item_id, inventory_item_id,
    legacy_source_key, item_name, qty, unit, unit_price, total,
    cost_total, created_at
)
SELECT
    receipt.id,
    source.account_id,
    COALESCE(inventory.catalog_item_id, catalog.id),
    CASE WHEN inventory.track_stock THEN inventory.id ELSE NULL END,
    source.resource || ':' || source.source_key,
    left(COALESCE(
        NULLIF(source.row_data->>'item_name', ''),
        NULLIF(source.row_data->>'name', ''),
        NULLIF(source.row_data->>'title', ''),
        NULLIF(source.row_data->>'description', ''),
        'Kassa harakati'
    ), 220),
    CASE WHEN COALESCE(source.row_data->>'qty', '')
        ~ '^[0-9]+([.][0-9]+)?$'
         AND (source.row_data->>'qty')::numeric > 0
        THEN round((source.row_data->>'qty')::numeric, 3) ELSE 1 END,
    left(COALESCE(NULLIF(source.row_data->>'unit', ''), 'dona'), 40),
    CASE WHEN COALESCE(source.row_data->>'price', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'price')::bigint ELSE 0 END,
    CASE
        WHEN COALESCE(source.row_data->>'total', '') ~ '^[0-9]+$'
            THEN greatest(1, (source.row_data->>'total')::bigint)
        WHEN COALESCE(source.row_data->>'amount', '') ~ '^[0-9]+$'
            THEN greatest(1, (source.row_data->>'amount')::bigint)
        ELSE 1
    END,
    CASE WHEN COALESCE(source.row_data->>'cost_total', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'cost_total')::bigint ELSE 0 END,
    CASE WHEN COALESCE(source.row_data->>'created_at', '')
        ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((source.row_data->>'created_at')::double precision)
        ELSE receipt.created_at END
FROM source_rows AS source
JOIN cash_receipts AS receipt
  ON receipt.business_account_id = source.account_id
 AND receipt.legacy_group_key = source.group_key
LEFT JOIN inventory_items AS inventory
  ON inventory.business_account_id = source.account_id
 AND inventory.legacy_source_id = CASE
    WHEN COALESCE(source.row_data->>'item_id', '') ~ '^[0-9]+$'
    THEN (source.row_data->>'item_id')::bigint ELSE NULL END
LEFT JOIN catalog_items AS catalog
  ON catalog.business_account_id = source.account_id
 AND catalog.source_record_key = CASE
    WHEN COALESCE(source.row_data->>'item_id', '') ~ '^[0-9]+$'
    THEN source.row_data->>'item_id' ELSE NULL END
ON CONFLICT (business_account_id, legacy_source_key)
    WHERE legacy_source_key IS NOT NULL
DO UPDATE SET
    receipt_id = EXCLUDED.receipt_id,
    catalog_item_id = EXCLUDED.catalog_item_id,
    inventory_item_id = EXCLUDED.inventory_item_id,
    item_name = EXCLUDED.item_name,
    qty = EXCLUDED.qty,
    unit = EXCLUDED.unit,
    unit_price = EXCLUDED.unit_price,
    total = EXCLUDED.total,
    cost_total = EXCLUDED.cost_total
"""


COUNTER_BACKFILL_SQL = r"""
INSERT INTO cash_receipt_counters (
    business_account_id, last_receipt_no, updated_at
)
SELECT business_account_id, max(receipt_no), now()
FROM cash_receipts
WHERE receipt_no IS NOT NULL
GROUP BY business_account_id
ON CONFLICT (business_account_id) DO UPDATE SET
    last_receipt_no = greatest(
        cash_receipt_counters.last_receipt_no,
        EXCLUDED.last_receipt_no
    ),
    updated_at = now()
"""


CONSUMPTION_RELINK_SQL = r"""
UPDATE inventory_batch_consumptions AS consumption
SET source_type = 'cash_line', source_id = line.id
FROM cash_receipt_lines AS line
WHERE consumption.source_type = 'sale'
  AND consumption.source_id IS NOT NULL
  AND line.legacy_source_key = 'sales:' || consumption.source_id::text
"""


MOVE_RELINK_SQL = r"""
UPDATE inventory_stock_moves AS move
SET cash_sale_line_id = line.id
FROM cash_receipt_lines AS line
WHERE move.business_account_id = line.business_account_id
  AND move.note ~ '^Kassa #[0-9]+$'
  AND line.legacy_source_key = 'sales:' ||
      substring(move.note FROM 'Kassa #([0-9]+)')
"""


def upgrade() -> None:
    op.create_table(
        "cash_receipt_counters",
        sa.Column("business_account_id", sa.BigInteger(), primary_key=True),
        sa.Column("last_receipt_no", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "last_receipt_no >= 0",
            name="ck_cash_receipt_counters_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "cash_receipts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("receipt_no", sa.BigInteger()),
        sa.Column("source", sa.String(length=24), nullable=False, server_default="manual"),
        sa.Column("order_id", sa.BigInteger()),
        sa.Column("legacy_order_source_id", sa.BigInteger()),
        sa.Column("legacy_group_key", sa.String(length=160)),
        sa.Column("pay_type", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("debtor_name_snapshot", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("legacy_debtor_source_id", sa.BigInteger()),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by_staff_id", sa.BigInteger()),
        sa.Column("actor_name_snapshot", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source IN ('manual','order','dining','education','debt_payment')",
            name="ck_cash_receipts_source",
        ),
        sa.CheckConstraint(
            "pay_type IN ('','naqd','karta','qarz')",
            name="ck_cash_receipts_pay_type",
        ),
        sa.CheckConstraint(
            "receipt_no IS NULL OR receipt_no > 0",
            name="ck_cash_receipts_receipt_no_positive",
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["created_by_staff_id"], ["staff_members.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "business_account_id", "receipt_no",
            name="uq_cash_receipts_business_number",
        ),
        sa.UniqueConstraint("order_id", name="uq_cash_receipts_order"),
    )
    op.create_index(
        "ix_cash_receipts_business_created",
        "cash_receipts",
        ["business_account_id", "created_at", "id"],
    )
    op.create_index(
        "ix_cash_receipts_business_source",
        "cash_receipts",
        ["business_account_id", "source", "created_at"],
    )
    op.create_index(
        "uq_cash_receipts_legacy_group",
        "cash_receipts",
        ["business_account_id", "legacy_group_key"],
        unique=True,
        postgresql_where=sa.text("legacy_group_key IS NOT NULL"),
    )
    op.create_table(
        "cash_receipt_lines",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("receipt_id", sa.BigInteger(), nullable=False),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("catalog_item_id", sa.BigInteger()),
        sa.Column("inventory_item_id", sa.BigInteger()),
        sa.Column("legacy_source_key", sa.String(length=160)),
        sa.Column("item_name", sa.String(length=220), nullable=False),
        sa.Column("qty", sa.Numeric(15, 3), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False, server_default="dona"),
        sa.Column("unit_price", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cost_total", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_cash_receipt_lines_qty"),
        sa.CheckConstraint("unit_price >= 0", name="ck_cash_receipt_lines_price"),
        sa.CheckConstraint("total > 0", name="ck_cash_receipt_lines_total"),
        sa.CheckConstraint("cost_total >= 0", name="ck_cash_receipt_lines_cost"),
        sa.ForeignKeyConstraint(
            ["receipt_id"], ["cash_receipts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["catalog_item_id"], ["catalog_items.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["inventory_item_id"], ["inventory_items.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_cash_receipt_lines_receipt",
        "cash_receipt_lines",
        ["receipt_id", "id"],
    )
    op.create_index(
        "ix_cash_receipt_lines_catalog",
        "cash_receipt_lines",
        ["business_account_id", "catalog_item_id"],
    )
    op.create_index(
        "uq_cash_receipt_lines_legacy_source",
        "cash_receipt_lines",
        ["business_account_id", "legacy_source_key"],
        unique=True,
        postgresql_where=sa.text("legacy_source_key IS NOT NULL"),
    )
    op.add_column(
        "inventory_stock_moves",
        sa.Column("cash_sale_line_id", sa.BigInteger()),
    )
    op.create_index(
        "ix_inventory_stock_moves_cash_line",
        "inventory_stock_moves",
        ["cash_sale_line_id"],
    )

    op.execute(RECEIPT_BACKFILL_SQL)
    op.execute(LINE_BACKFILL_SQL)
    op.execute(COUNTER_BACKFILL_SQL)
    op.execute(CONSUMPTION_RELINK_SQL)
    op.execute(MOVE_RELINK_SQL)


def downgrade() -> None:
    op.drop_index("ix_inventory_stock_moves_cash_line", table_name="inventory_stock_moves")
    op.drop_column("inventory_stock_moves", "cash_sale_line_id")
    op.drop_index("uq_cash_receipt_lines_legacy_source", table_name="cash_receipt_lines")
    op.drop_index("ix_cash_receipt_lines_catalog", table_name="cash_receipt_lines")
    op.drop_index("ix_cash_receipt_lines_receipt", table_name="cash_receipt_lines")
    op.drop_table("cash_receipt_lines")
    op.drop_index("uq_cash_receipts_legacy_group", table_name="cash_receipts")
    op.drop_index("ix_cash_receipts_business_source", table_name="cash_receipts")
    op.drop_index("ix_cash_receipts_business_created", table_name="cash_receipts")
    op.drop_table("cash_receipts")
    op.drop_table("cash_receipt_counters")
