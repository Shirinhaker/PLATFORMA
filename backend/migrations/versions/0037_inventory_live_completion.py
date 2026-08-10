"""Omborga ulanmay qolgan jonli katalog mahsulotlarini yakuniy tenglash.

Revision ID: 0037_inventory_live_completion
Revises: 0036_subscription_payments

0015 migratsiyasidan keyin kabinetda yaratilgan, ammo eski umumiy CRUD sabab
`inventory_items`ga tushmagan mahsulotlargina qo‘shiladi. Mavjud Ombor qoldig‘i
hech qachon qayta yozilmaydi.
"""

from alembic import op


revision = "0037_inventory_live_completion"
down_revision = "0036_subscription_payments"
branch_labels = None
depends_on = None


BACKFILL_MISSING_ITEMS_SQL = r"""WITH
relational_rows AS (
    SELECT
        resource.account_id,
        record.source_key,
        record.ordinal,
        COALESCE(
            jsonb_object_agg(
                substr(field.path, 2),
                CASE field.value_type
                    WHEN 'null' THEN 'null'::jsonb
                    WHEN 'boolean' THEN to_jsonb(field.value_boolean)
                    WHEN 'integer' THEN to_jsonb(field.value_integer)
                    WHEN 'float' THEN to_jsonb(field.value_float)
                    ELSE to_jsonb(COALESCE(field.value_text, ''))
                END
            ) FILTER (WHERE field.path ~ '^/[^/]+$'),
            '{}'::jsonb
        ) AS row_data,
        0 AS priority
    FROM cabinet_resources AS resource
    JOIN cabinet_records AS record ON record.resource_id = resource.id
    LEFT JOIN cabinet_record_fields AS field ON field.record_id = record.id
    WHERE resource.account_type = 'business'
      AND resource.resource = 'items'
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
        CASE
            WHEN jsonb_typeof(
                COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'items'
            ) = 'array'
            THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'items'
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
),
source_rows AS (
    SELECT DISTINCT ON (account_id, source_key)
        account_id, source_key, row_data
    FROM (
        SELECT * FROM relational_rows
        UNION ALL
        SELECT * FROM payload_rows
    ) AS ranked
    ORDER BY account_id, source_key, priority, ordinal
)
INSERT INTO inventory_items (
    business_account_id, catalog_item_id, legacy_source_id, track_stock,
    stock_type, stock_qty, cost_price, min_qty, fifo_initialized,
    created_at, updated_at
)
SELECT
    source.account_id,
    catalog.id,
    CASE WHEN source.source_key ~ '^[0-9]+$'
        THEN source.source_key::bigint ELSE NULL END,
    true,
    CASE WHEN source.row_data->>'stock_type' = 'raw_material'
        THEN 'raw_material' ELSE 'ready_food' END,
    CASE WHEN COALESCE(source.row_data->>'stock_qty', '')
        ~ '^[0-9]+([.][0-9]+)?$'
        THEN round((source.row_data->>'stock_qty')::numeric, 3) ELSE 0 END,
    CASE WHEN COALESCE(source.row_data->>'cost_price', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'cost_price')::bigint ELSE 0 END,
    CASE WHEN COALESCE(source.row_data->>'min_qty', '')
        ~ '^[0-9]+([.][0-9]+)?$'
        THEN round((source.row_data->>'min_qty')::numeric, 3) ELSE 0 END,
    true,
    now(),
    now()
FROM source_rows AS source
JOIN catalog_items AS catalog
  ON catalog.business_account_id = source.account_id
 AND catalog.source_record_key = source.source_key
WHERE catalog.kind = 'product'
  AND lower(COALESCE(source.row_data->>'track_stock', '0'))
      IN ('1', 'true', 'yes', 'on')
  AND NOT EXISTS (
      SELECT 1 FROM inventory_items AS existing
      WHERE existing.catalog_item_id = catalog.id
  )
ON CONFLICT (catalog_item_id) DO NOTHING
"""


BACKFILL_MISSING_FIFO_SQL = r"""INSERT INTO inventory_stock_batches (
    business_account_id, inventory_item_id, legacy_source_id, qty_in,
    qty_remaining, unit_cost, source_move_id, created_at
)
SELECT
    item.business_account_id, item.id, NULL, item.stock_qty,
    item.stock_qty, item.cost_price, NULL, item.created_at
FROM inventory_items AS item
WHERE item.stock_qty > 0
  AND NOT EXISTS (
      SELECT 1 FROM inventory_stock_batches AS batch
      WHERE batch.inventory_item_id = item.id
  )
"""


def upgrade() -> None:
    op.execute(BACKFILL_MISSING_ITEMS_SQL)
    op.execute(BACKFILL_MISSING_FIFO_SQL)


def downgrade() -> None:
    # Bu faqat mavjud biznes ma’lumotini tenglaydigan data migration.
    # Downgrade haqiqiy Ombor tarixini o‘chirib yubormasligi kerak.
    pass
