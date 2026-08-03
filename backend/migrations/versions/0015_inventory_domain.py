"""Ombor, FIFO, retsept va ishlab chiqarish domenini ko'chirish.

Revision ID: 0015_inventory_domain
Revises: 0014_staff_domain
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_inventory_domain"
down_revision = "0014_staff_domain"
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


def _relational_rows(resources: str) -> str:
    return rf"""
relational_rows AS (
    SELECT
        resource.account_id,
        resource.resource,
        record.source_key,
        record.ordinal,
        COALESCE(
            jsonb_object_agg(
                substr(field.path, 2),
                {JSON_VALUE_SQL}
            ) FILTER (WHERE field.path ~ '^/[^/]+$'),
            '{{}}'::jsonb
        ) AS row_data,
        0 AS priority
    FROM cabinet_resources AS resource
    JOIN cabinet_records AS record ON record.resource_id = resource.id
    LEFT JOIN cabinet_record_fields AS field ON field.record_id = record.id
    WHERE resource.account_type = 'business'
      AND resource.resource IN ({resources})
    GROUP BY resource.account_id, resource.resource, record.id,
             record.source_key, record.ordinal
)
"""


def _payload_rows(resources: tuple[str, ...]) -> str:
    values = ", ".join(f"('{resource}')" for resource in resources)
    return rf"""
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
    CROSS JOIN LATERAL (VALUES {values}) AS resource_name(resource)
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(
                COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
                -> resource_name.resource
            ) = 'array'
            THEN COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
                -> resource_name.resource
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
)
"""


ITEM_SOURCE_CTES = (
    "WITH\n"
    + _relational_rows("'items', 'warehouse_items'").strip()
    + ",\n"
    + _payload_rows(("items", "warehouse_items")).strip()
    + r""",
source_rows AS (
    SELECT DISTINCT ON (account_id, legacy_source_id)
        account_id, legacy_source_id, row_data
    FROM (
        SELECT
            account_id,
            CASE
                WHEN COALESCE(row_data->>'id', source_key, '') ~ '^[0-9]+$'
                THEN COALESCE(row_data->>'id', source_key)::bigint
                ELSE NULL
            END AS legacy_source_id,
            row_data,
            priority,
            CASE resource WHEN 'items' THEN 0 ELSE 1 END AS resource_priority,
            ordinal
        FROM relational_rows
        UNION ALL
        SELECT
            account_id,
            CASE
                WHEN COALESCE(row_data->>'id', source_key, '') ~ '^[0-9]+$'
                THEN COALESCE(row_data->>'id', source_key)::bigint
                ELSE NULL
            END,
            row_data,
            priority,
            CASE resource WHEN 'items' THEN 0 ELSE 1 END,
            ordinal
        FROM payload_rows
    ) AS ranked
    WHERE legacy_source_id IS NOT NULL
    ORDER BY account_id, legacy_source_id, priority, resource_priority, ordinal
)
"""
)


INVENTORY_ITEM_BACKFILL_SQL = ITEM_SOURCE_CTES + r"""
INSERT INTO inventory_items (
    business_account_id, catalog_item_id, legacy_source_id, track_stock,
    stock_type, stock_qty, cost_price, min_qty, fifo_initialized,
    created_at, updated_at
)
SELECT
    source.account_id,
    catalog.id,
    source.legacy_source_id,
    true,
    CASE WHEN source.row_data->>'stock_type' = 'raw_material'
        THEN 'raw_material' ELSE 'ready_food' END,
    CASE WHEN COALESCE(source.row_data->>'stock_qty', '')
        ~ '^-?[0-9]+([.][0-9]+)?$'
        THEN round((source.row_data->>'stock_qty')::numeric, 3) ELSE 0 END,
    CASE WHEN COALESCE(source.row_data->>'cost_price', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'cost_price')::bigint ELSE 0 END,
    CASE WHEN COALESCE(source.row_data->>'min_qty', '')
        ~ '^[0-9]+([.][0-9]+)?$'
        THEN round((source.row_data->>'min_qty')::numeric, 3) ELSE 0 END,
    true,
    CASE WHEN COALESCE(source.row_data->>'created_at', '') ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((source.row_data->>'created_at')::double precision)
        ELSE now() END,
    now()
FROM source_rows AS source
JOIN catalog_items AS catalog
  ON catalog.business_account_id = source.account_id
 AND catalog.source_record_key = source.legacy_source_id::text
WHERE lower(COALESCE(source.row_data->>'track_stock', '0'))
    IN ('1', 'true', 'yes', 'on')
ON CONFLICT (catalog_item_id) DO UPDATE SET
    legacy_source_id = EXCLUDED.legacy_source_id,
    track_stock = EXCLUDED.track_stock,
    stock_type = EXCLUDED.stock_type,
    stock_qty = EXCLUDED.stock_qty,
    cost_price = EXCLUDED.cost_price,
    min_qty = EXCLUDED.min_qty,
    fifo_initialized = EXCLUDED.fifo_initialized,
    updated_at = now()
"""


MOVE_SOURCE_CTES = (
    "WITH\n"
    + _relational_rows("'stock_moves', 'warehouse_tx'").strip()
    + ",\n"
    + _payload_rows(("stock_moves", "warehouse_tx")).strip()
    + r""",
source_rows AS (
    SELECT DISTINCT ON (account_id, legacy_source_id)
        account_id, legacy_source_id, row_data
    FROM (
        SELECT
            account_id,
            CASE WHEN COALESCE(row_data->>'id', source_key, '') ~ '^[0-9]+$'
                THEN COALESCE(row_data->>'id', source_key)::bigint ELSE NULL END
                AS legacy_source_id,
            row_data, priority,
            CASE resource WHEN 'stock_moves' THEN 0 ELSE 1 END AS resource_priority,
            ordinal
        FROM relational_rows
        UNION ALL
        SELECT
            account_id,
            CASE WHEN COALESCE(row_data->>'id', source_key, '') ~ '^[0-9]+$'
                THEN COALESCE(row_data->>'id', source_key)::bigint ELSE NULL END,
            row_data, priority,
            CASE resource WHEN 'stock_moves' THEN 0 ELSE 1 END,
            ordinal
        FROM payload_rows
    ) AS ranked
    WHERE legacy_source_id IS NOT NULL
    ORDER BY account_id, legacy_source_id, priority, resource_priority, ordinal
)
"""
)


STOCK_MOVE_BACKFILL_SQL = MOVE_SOURCE_CTES + r"""
INSERT INTO inventory_stock_moves (
    business_account_id, inventory_item_id, legacy_source_id, delta,
    reason, note, cost, legacy_order_source_id, performed_by_staff_id, created_at
)
SELECT
    source.account_id,
    item.id,
    source.legacy_source_id,
    round((source.row_data->>'delta')::numeric, 3),
    CASE WHEN source.row_data->>'reason' IN ('kirim','chiqim','sotuv','tuzatish')
        THEN source.row_data->>'reason'
        WHEN (source.row_data->>'delta')::numeric > 0 THEN 'kirim'
        ELSE 'chiqim' END,
    left(COALESCE(source.row_data->>'note', ''), 200),
    CASE WHEN COALESCE(source.row_data->>'cost', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'cost')::bigint ELSE 0 END,
    CASE WHEN COALESCE(source.row_data->>'order_id', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'order_id')::bigint ELSE NULL END,
    NULL::bigint,
    CASE WHEN COALESCE(source.row_data->>'created_at', '') ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((source.row_data->>'created_at')::double precision)
        ELSE now() END
FROM source_rows AS source
JOIN inventory_items AS item
  ON item.business_account_id = source.account_id
 AND item.legacy_source_id = CASE
    WHEN COALESCE(source.row_data->>'item_id', '') ~ '^[0-9]+$'
    THEN (source.row_data->>'item_id')::bigint ELSE NULL END
WHERE COALESCE(source.row_data->>'delta', '') ~ '^-?[0-9]+([.][0-9]+)?$'
  AND (source.row_data->>'delta')::numeric <> 0
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO UPDATE SET
    inventory_item_id = EXCLUDED.inventory_item_id,
    delta = EXCLUDED.delta,
    reason = EXCLUDED.reason,
    note = EXCLUDED.note,
    cost = EXCLUDED.cost,
    legacy_order_source_id = EXCLUDED.legacy_order_source_id
"""


def _payload_source(resource: str) -> str:
    return rf"""WITH
source_rows AS (
    SELECT
        profile.account_id,
        CASE WHEN COALESCE(entry.row_data->>'id', '') ~ '^[0-9]+$'
            THEN (entry.row_data->>'id')::bigint ELSE NULL END AS legacy_source_id,
        entry.row_data
    FROM business_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(
            COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)->'{resource}'
        ) = 'array'
        THEN COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)->'{resource}'
        ELSE '[]'::jsonb END
    ) AS entry(row_data)
)
"""


STOCK_BATCH_BACKFILL_SQL = _payload_source("stock_batches") + r"""
INSERT INTO inventory_stock_batches (
    business_account_id, inventory_item_id, legacy_source_id, qty_in,
    qty_remaining, unit_cost, source_move_id, created_at
)
SELECT
    source.account_id,
    item.id,
    source.legacy_source_id,
    round((source.row_data->>'qty_in')::numeric, 3),
    greatest(0, least(
        round((source.row_data->>'qty_in')::numeric, 3),
        round((source.row_data->>'qty_remaining')::numeric, 3)
    )),
    CASE WHEN COALESCE(source.row_data->>'unit_cost', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'unit_cost')::bigint ELSE 0 END,
    move.id,
    CASE WHEN COALESCE(source.row_data->>'created_at', '') ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((source.row_data->>'created_at')::double precision)
        ELSE now() END
FROM source_rows AS source
JOIN inventory_items AS item
  ON item.business_account_id = source.account_id
 AND item.legacy_source_id = CASE
    WHEN COALESCE(source.row_data->>'item_id', '') ~ '^[0-9]+$'
    THEN (source.row_data->>'item_id')::bigint ELSE NULL END
LEFT JOIN inventory_stock_moves AS move
  ON move.business_account_id = source.account_id
 AND move.legacy_source_id = CASE
    WHEN COALESCE(source.row_data->>'source_move_id', '') ~ '^[0-9]+$'
    THEN (source.row_data->>'source_move_id')::bigint ELSE NULL END
WHERE source.legacy_source_id IS NOT NULL
  AND COALESCE(source.row_data->>'qty_in', '') ~ '^[0-9]+([.][0-9]+)?$'
  AND COALESCE(source.row_data->>'qty_remaining', '') ~ '^[0-9]+([.][0-9]+)?$'
  AND (source.row_data->>'qty_in')::numeric > 0
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO UPDATE SET
    inventory_item_id = EXCLUDED.inventory_item_id,
    qty_in = EXCLUDED.qty_in,
    qty_remaining = EXCLUDED.qty_remaining,
    unit_cost = EXCLUDED.unit_cost,
    source_move_id = EXCLUDED.source_move_id
"""


INITIAL_FIFO_BACKFILL_SQL = r"""WITH
missing AS (
    SELECT item.*
    FROM inventory_items AS item
    WHERE item.stock_qty > 0
      AND NOT EXISTS (
        SELECT 1 FROM inventory_stock_batches AS batch
        WHERE batch.inventory_item_id = item.id
      )
)
INSERT INTO inventory_stock_batches (
    business_account_id, inventory_item_id, legacy_source_id, qty_in,
    qty_remaining, unit_cost, source_move_id, created_at
)
SELECT business_account_id, id, NULL, stock_qty, stock_qty, cost_price, NULL, created_at
FROM missing
"""


RECIPE_BACKFILL_SQL = _payload_source("item_recipes") + r"""
INSERT INTO inventory_recipe_ingredients (
    business_account_id, ready_inventory_item_id,
    ingredient_inventory_item_id, legacy_source_id, qty_per_unit, updated_at
)
SELECT
    source.account_id,
    ready.id,
    ingredient.id,
    source.legacy_source_id,
    round((source.row_data->>'qty_per_unit')::numeric, 6),
    CASE WHEN COALESCE(source.row_data->>'updated_at', '') ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((source.row_data->>'updated_at')::double precision)
        ELSE now() END
FROM source_rows AS source
JOIN inventory_items AS ready
  ON ready.business_account_id = source.account_id
 AND ready.legacy_source_id = CASE
    WHEN COALESCE(source.row_data->>'ready_item_id', '') ~ '^[0-9]+$'
    THEN (source.row_data->>'ready_item_id')::bigint ELSE NULL END
JOIN inventory_items AS ingredient
  ON ingredient.business_account_id = source.account_id
 AND ingredient.legacy_source_id = CASE
    WHEN COALESCE(source.row_data->>'ingredient_item_id', '') ~ '^[0-9]+$'
    THEN (source.row_data->>'ingredient_item_id')::bigint ELSE NULL END
WHERE COALESCE(source.row_data->>'qty_per_unit', '') ~ '^[0-9]+([.][0-9]+)?$'
  AND (source.row_data->>'qty_per_unit')::numeric > 0
ON CONFLICT (
    business_account_id, ready_inventory_item_id, ingredient_inventory_item_id
) DO UPDATE SET
    legacy_source_id = EXCLUDED.legacy_source_id,
    qty_per_unit = EXCLUDED.qty_per_unit,
    updated_at = EXCLUDED.updated_at
"""


PRODUCTION_BATCH_BACKFILL_SQL = _payload_source("production_batches") + r"""
INSERT INTO inventory_production_batches (
    business_account_id, ready_inventory_item_id, legacy_source_id, qty,
    total_cost, unit_cost, note, performed_by_staff_id, created_at
)
SELECT
    source.account_id,
    item.id,
    source.legacy_source_id,
    round((source.row_data->>'qty')::numeric, 3),
    CASE WHEN COALESCE(source.row_data->>'total_cost', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'total_cost')::bigint ELSE 0 END,
    CASE WHEN COALESCE(source.row_data->>'unit_cost', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'unit_cost')::bigint ELSE 0 END,
    left(COALESCE(source.row_data->>'note', ''), 200),
    NULL::bigint,
    CASE WHEN COALESCE(source.row_data->>'created_at', '') ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((source.row_data->>'created_at')::double precision)
        ELSE now() END
FROM source_rows AS source
JOIN inventory_items AS item
  ON item.business_account_id = source.account_id
 AND item.legacy_source_id = CASE
    WHEN COALESCE(source.row_data->>'ready_item_id', '') ~ '^[0-9]+$'
    THEN (source.row_data->>'ready_item_id')::bigint ELSE NULL END
WHERE source.legacy_source_id IS NOT NULL
  AND COALESCE(source.row_data->>'qty', '') ~ '^[0-9]+([.][0-9]+)?$'
  AND (source.row_data->>'qty')::numeric > 0
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO UPDATE SET
    ready_inventory_item_id = EXCLUDED.ready_inventory_item_id,
    qty = EXCLUDED.qty,
    total_cost = EXCLUDED.total_cost,
    unit_cost = EXCLUDED.unit_cost,
    note = EXCLUDED.note
"""


PRODUCTION_INPUT_BACKFILL_SQL = _payload_source("production_batches") + r""",
inputs AS (
    SELECT
        source.account_id,
        source.legacy_source_id AS production_legacy_id,
        entry.ordinality::bigint AS ordinal,
        entry.row_data
    FROM source_rows AS source
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(source.row_data->'inputs') = 'array'
            THEN source.row_data->'inputs' ELSE '[]'::jsonb END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
)
INSERT INTO inventory_production_inputs (
    production_batch_id, inventory_item_id, legacy_source_id,
    qty, unit_cost, total_cost
)
SELECT
    production.id,
    item.id,
    CASE WHEN COALESCE(input.row_data->>'id', '') ~ '^[0-9]+$'
        THEN (input.row_data->>'id')::bigint ELSE input.ordinal END,
    round((input.row_data->>'qty')::numeric, 3),
    CASE WHEN COALESCE(input.row_data->>'unit_cost', '') ~ '^[0-9]+$'
        THEN (input.row_data->>'unit_cost')::bigint ELSE 0 END,
    CASE WHEN COALESCE(input.row_data->>'total_cost', '') ~ '^[0-9]+$'
        THEN (input.row_data->>'total_cost')::bigint ELSE 0 END
FROM inputs AS input
JOIN inventory_production_batches AS production
  ON production.business_account_id = input.account_id
 AND production.legacy_source_id = input.production_legacy_id
JOIN inventory_items AS item
  ON item.business_account_id = input.account_id
 AND item.legacy_source_id = CASE
    WHEN COALESCE(input.row_data->>'item_id', '') ~ '^[0-9]+$'
    THEN (input.row_data->>'item_id')::bigint ELSE NULL END
WHERE COALESCE(input.row_data->>'qty', '') ~ '^[0-9]+([.][0-9]+)?$'
  AND (input.row_data->>'qty')::numeric > 0
ON CONFLICT (production_batch_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO UPDATE SET
    inventory_item_id = EXCLUDED.inventory_item_id,
    qty = EXCLUDED.qty,
    unit_cost = EXCLUDED.unit_cost,
    total_cost = EXCLUDED.total_cost
"""


CONSUMPTION_BACKFILL_SQL = _payload_source("stock_batches") + r""",
consumptions AS (
    SELECT
        source.account_id,
        source.legacy_source_id AS batch_legacy_id,
        entry.ordinality::bigint AS ordinal,
        entry.row_data
    FROM source_rows AS source
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(source.row_data->'consumptions') = 'array'
            THEN source.row_data->'consumptions' ELSE '[]'::jsonb END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
),
resolved AS (
    SELECT
        input.*,
        batch.id AS target_batch_id,
        item.id AS target_item_id,
        move.id AS target_move_id,
        production.id AS target_production_id
    FROM consumptions AS input
    JOIN inventory_stock_batches AS batch
      ON batch.business_account_id = input.account_id
     AND batch.legacy_source_id = input.batch_legacy_id
    JOIN inventory_items AS item
      ON item.business_account_id = input.account_id
     AND item.legacy_source_id = CASE
        WHEN COALESCE(input.row_data->>'item_id', '') ~ '^[0-9]+$'
        THEN (input.row_data->>'item_id')::bigint ELSE NULL END
    LEFT JOIN inventory_stock_moves AS move
      ON move.business_account_id = input.account_id
     AND move.legacy_source_id = CASE
        WHEN input.row_data->>'source_type' = 'stock_move'
         AND COALESCE(input.row_data->>'source_id', '') ~ '^[0-9]+$'
        THEN (input.row_data->>'source_id')::bigint ELSE NULL END
    LEFT JOIN inventory_production_batches AS production
      ON production.business_account_id = input.account_id
     AND production.legacy_source_id = CASE
        WHEN input.row_data->>'source_type' = 'production'
         AND COALESCE(input.row_data->>'source_id', '') ~ '^[0-9]+$'
        THEN (input.row_data->>'source_id')::bigint ELSE NULL END
)
INSERT INTO inventory_batch_consumptions (
    batch_id, inventory_item_id, legacy_source_id, qty, unit_cost,
    total_cost, source_type, source_id, created_at
)
SELECT
    target_batch_id,
    target_item_id,
    CASE WHEN COALESCE(row_data->>'id', '') ~ '^[0-9]+$'
        THEN (row_data->>'id')::bigint ELSE ordinal END,
    round((row_data->>'qty')::numeric, 3),
    CASE WHEN COALESCE(row_data->>'unit_cost', '') ~ '^[0-9]+$'
        THEN (row_data->>'unit_cost')::bigint ELSE 0 END,
    CASE WHEN COALESCE(row_data->>'total_cost', '') ~ '^[0-9]+$'
        THEN (row_data->>'total_cost')::bigint ELSE 0 END,
    left(COALESCE(row_data->>'source_type', ''), 32),
    CASE
        WHEN row_data->>'source_type' = 'stock_move' THEN target_move_id
        WHEN row_data->>'source_type' = 'production' THEN target_production_id
        WHEN COALESCE(row_data->>'source_id', '') ~ '^[0-9]+$'
            THEN (row_data->>'source_id')::bigint
        ELSE NULL
    END,
    CASE WHEN COALESCE(row_data->>'created_at', '') ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((row_data->>'created_at')::double precision)
        ELSE now() END
FROM resolved
WHERE COALESCE(row_data->>'qty', '') ~ '^[0-9]+([.][0-9]+)?$'
  AND (row_data->>'qty')::numeric > 0
ON CONFLICT (batch_id, legacy_source_id) WHERE legacy_source_id IS NOT NULL
DO UPDATE SET
    batch_id = EXCLUDED.batch_id,
    inventory_item_id = EXCLUDED.inventory_item_id,
    qty = EXCLUDED.qty,
    unit_cost = EXCLUDED.unit_cost,
    total_cost = EXCLUDED.total_cost,
    source_type = EXCLUDED.source_type,
    source_id = EXCLUDED.source_id
"""


def upgrade() -> None:
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("catalog_item_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("track_stock", sa.Boolean(), nullable=False),
        sa.Column("stock_type", sa.String(length=24), nullable=False),
        sa.Column("stock_qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("cost_price", sa.BigInteger(), nullable=False),
        sa.Column("min_qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("fifo_initialized", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "stock_type IN ('ready_food', 'raw_material')",
            name="ck_inventory_items_stock_type",
        ),
        sa.CheckConstraint("cost_price >= 0", name="ck_inventory_items_cost_price"),
        sa.CheckConstraint("min_qty >= 0", name="ck_inventory_items_min_qty"),
        sa.ForeignKeyConstraint(["business_account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["catalog_item_id"], ["catalog_items.id"], ondelete="CASCADE"),
    )
    op.create_index("uq_inventory_items_catalog", "inventory_items", ["catalog_item_id"], unique=True)
    op.create_index(
        "uq_inventory_items_business_legacy", "inventory_items",
        ["business_account_id", "legacy_source_id"], unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "ix_inventory_items_business_tracked", "inventory_items",
        ["business_account_id", "track_stock", "stock_type"],
    )

    op.create_table(
        "inventory_stock_moves",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("inventory_item_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("delta", sa.Numeric(18, 3), nullable=False),
        sa.Column("reason", sa.String(length=20), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=False),
        sa.Column("cost", sa.BigInteger(), nullable=False),
        sa.Column("legacy_order_source_id", sa.BigInteger()),
        sa.Column("performed_by_staff_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("delta <> 0", name="ck_inventory_stock_moves_delta"),
        sa.CheckConstraint("cost >= 0", name="ck_inventory_stock_moves_cost"),
        sa.CheckConstraint(
            "reason IN ('kirim', 'chiqim', 'sotuv', 'tuzatish')",
            name="ck_inventory_stock_moves_reason",
        ),
        sa.ForeignKeyConstraint(["business_account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["performed_by_staff_id"], ["staff_members.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "uq_inventory_stock_moves_business_legacy", "inventory_stock_moves",
        ["business_account_id", "legacy_source_id"], unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "ix_inventory_stock_moves_item_created", "inventory_stock_moves",
        ["business_account_id", "inventory_item_id", "created_at", "id"],
    )

    op.create_table(
        "inventory_stock_batches",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("inventory_item_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("qty_in", sa.Numeric(18, 3), nullable=False),
        sa.Column("qty_remaining", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.BigInteger(), nullable=False),
        sa.Column("source_move_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("qty_in > 0", name="ck_inventory_stock_batches_qty_in"),
        sa.CheckConstraint(
            "qty_remaining >= 0 AND qty_remaining <= qty_in",
            name="ck_inventory_stock_batches_remaining",
        ),
        sa.CheckConstraint("unit_cost >= 0", name="ck_inventory_stock_batches_unit_cost"),
        sa.ForeignKeyConstraint(["business_account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_move_id"], ["inventory_stock_moves.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "uq_inventory_stock_batches_business_legacy", "inventory_stock_batches",
        ["business_account_id", "legacy_source_id"], unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "ix_inventory_stock_batches_fifo", "inventory_stock_batches",
        ["business_account_id", "inventory_item_id", "created_at", "id"],
    )

    op.create_table(
        "inventory_batch_consumptions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("inventory_item_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.BigInteger(), nullable=False),
        sa.Column("total_cost", sa.BigInteger(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_inventory_consumptions_qty"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_inventory_consumptions_unit_cost"),
        sa.CheckConstraint("total_cost >= 0", name="ck_inventory_consumptions_total_cost"),
        sa.ForeignKeyConstraint(["batch_id"], ["inventory_stock_batches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "uq_inventory_consumptions_batch_legacy", "inventory_batch_consumptions",
        ["batch_id", "legacy_source_id"], unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "ix_inventory_consumptions_source", "inventory_batch_consumptions",
        ["source_type", "source_id", "id"],
    )

    op.create_table(
        "inventory_recipe_ingredients",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("ready_inventory_item_id", sa.BigInteger(), nullable=False),
        sa.Column("ingredient_inventory_item_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("qty_per_unit", sa.Numeric(18, 6), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("qty_per_unit > 0", name="ck_inventory_recipes_qty"),
        sa.ForeignKeyConstraint(["business_account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ready_inventory_item_id"], ["inventory_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingredient_inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "uq_inventory_recipes_items", "inventory_recipe_ingredients",
        ["business_account_id", "ready_inventory_item_id", "ingredient_inventory_item_id"],
        unique=True,
    )
    op.create_index(
        "uq_inventory_recipes_business_legacy", "inventory_recipe_ingredients",
        ["business_account_id", "legacy_source_id"], unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )

    op.create_table(
        "inventory_production_batches",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("ready_inventory_item_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("total_cost", sa.BigInteger(), nullable=False),
        sa.Column("unit_cost", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=False),
        sa.Column("performed_by_staff_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_inventory_production_qty"),
        sa.CheckConstraint("total_cost >= 0", name="ck_inventory_production_total_cost"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_inventory_production_unit_cost"),
        sa.ForeignKeyConstraint(["business_account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ready_inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["performed_by_staff_id"], ["staff_members.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "uq_inventory_production_business_legacy", "inventory_production_batches",
        ["business_account_id", "legacy_source_id"], unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "ix_inventory_production_business_created", "inventory_production_batches",
        ["business_account_id", "created_at", "id"],
    )

    op.create_table(
        "inventory_production_inputs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("production_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("inventory_item_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.BigInteger(), nullable=False),
        sa.Column("total_cost", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_inventory_production_inputs_qty"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_inventory_production_inputs_unit_cost"),
        sa.CheckConstraint("total_cost >= 0", name="ck_inventory_production_inputs_total_cost"),
        sa.ForeignKeyConstraint(["production_batch_id"], ["inventory_production_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "uq_inventory_production_inputs_legacy", "inventory_production_inputs",
        ["production_batch_id", "legacy_source_id"], unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )

    op.execute(INVENTORY_ITEM_BACKFILL_SQL)
    op.execute(STOCK_MOVE_BACKFILL_SQL)
    op.execute(STOCK_BATCH_BACKFILL_SQL)
    op.execute(INITIAL_FIFO_BACKFILL_SQL)
    op.execute(RECIPE_BACKFILL_SQL)
    op.execute(PRODUCTION_BATCH_BACKFILL_SQL)
    op.execute(PRODUCTION_INPUT_BACKFILL_SQL)
    op.execute(CONSUMPTION_BACKFILL_SQL)


def downgrade() -> None:
    op.drop_index("uq_inventory_production_inputs_legacy", table_name="inventory_production_inputs")
    op.drop_table("inventory_production_inputs")
    op.drop_index("ix_inventory_production_business_created", table_name="inventory_production_batches")
    op.drop_index("uq_inventory_production_business_legacy", table_name="inventory_production_batches")
    op.drop_table("inventory_production_batches")
    op.drop_index("uq_inventory_recipes_business_legacy", table_name="inventory_recipe_ingredients")
    op.drop_index("uq_inventory_recipes_items", table_name="inventory_recipe_ingredients")
    op.drop_table("inventory_recipe_ingredients")
    op.drop_index("ix_inventory_consumptions_source", table_name="inventory_batch_consumptions")
    op.drop_index("uq_inventory_consumptions_batch_legacy", table_name="inventory_batch_consumptions")
    op.drop_table("inventory_batch_consumptions")
    op.drop_index("ix_inventory_stock_batches_fifo", table_name="inventory_stock_batches")
    op.drop_index("uq_inventory_stock_batches_business_legacy", table_name="inventory_stock_batches")
    op.drop_table("inventory_stock_batches")
    op.drop_index("ix_inventory_stock_moves_item_created", table_name="inventory_stock_moves")
    op.drop_index("uq_inventory_stock_moves_business_legacy", table_name="inventory_stock_moves")
    op.drop_table("inventory_stock_moves")
    op.drop_index("ix_inventory_items_business_tracked", table_name="inventory_items")
    op.drop_index("uq_inventory_items_business_legacy", table_name="inventory_items")
    op.drop_index("uq_inventory_items_catalog", table_name="inventory_items")
    op.drop_table("inventory_items")
