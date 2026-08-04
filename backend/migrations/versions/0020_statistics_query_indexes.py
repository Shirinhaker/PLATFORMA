"""Statistika so‘rovlari va ofitsiant atributsiyasini ko‘chirish."""

from alembic import op
import sqlalchemy as sa


revision = "0020_statistics_query_indexes"
down_revision = "0019_education_domain"
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


WAITER_BACKFILL_SQL = rf"""
WITH relational_rows AS (
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
      AND resource.resource IN ('dining_bookings', 'dining_orders')
    GROUP BY resource.account_id, resource.resource, record.id,
             record.source_key, record.ordinal
),
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
        VALUES ('dining_bookings'), ('dining_orders')
    ) AS resource_name(resource)
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(
            COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
            -> resource_name.resource
        ) = 'array'
        THEN COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
            -> resource_name.resource
        ELSE '[]'::jsonb END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
),
source_rows AS (
    SELECT DISTINCT ON (account_id, source_key)
        account_id, source_key, row_data
    FROM (
        SELECT * FROM relational_rows
        UNION ALL
        SELECT * FROM payload_rows
    ) AS candidates
    ORDER BY account_id, source_key, priority,
             CASE WHEN resource = 'dining_bookings' THEN 0 ELSE 1 END,
             ordinal
)
UPDATE cash_receipts AS receipt
SET waiter_staff_id = staff.id,
    waiter_name_snapshot = left(COALESCE(
        NULLIF(source.row_data->>'waiter_name', ''),
        receipt.waiter_name_snapshot,
        ''
    ), 160)
FROM source_rows AS source
LEFT JOIN staff_members AS staff
  ON staff.business_account_id = source.account_id
 AND staff.legacy_source_id = CASE
    WHEN COALESCE(source.row_data->>'waiter_staff_id', '') ~ '^[0-9]+$'
    THEN (source.row_data->>'waiter_staff_id')::bigint
    ELSE NULL END
WHERE receipt.business_account_id = source.account_id
  AND receipt.source = 'dining'
  AND receipt.legacy_order_source_id IS NOT NULL
  AND receipt.legacy_order_source_id = CASE
    WHEN COALESCE(source.row_data->>'id', source.source_key, '') ~ '^[0-9]+$'
    THEN COALESCE(source.row_data->>'id', source.source_key)::bigint
    ELSE NULL END
"""


def upgrade() -> None:
    op.add_column(
        "cash_receipts",
        sa.Column("waiter_staff_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "cash_receipts",
        sa.Column(
            "waiter_name_snapshot",
            sa.String(length=160),
            nullable=False,
            server_default="",
        ),
    )
    op.create_foreign_key(
        "fk_cash_receipts_waiter_staff",
        "cash_receipts",
        "staff_members",
        ["waiter_staff_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(WAITER_BACKFILL_SQL)
    op.create_index(
        "ix_inventory_items_business_stock_qty",
        "inventory_items",
        ["business_account_id", "stock_qty", "id"],
        postgresql_where=sa.text("track_stock IS true"),
        sqlite_where=sa.text("track_stock = 1"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inventory_items_business_stock_qty",
        table_name="inventory_items",
    )
    op.drop_constraint(
        "fk_cash_receipts_waiter_staff",
        "cash_receipts",
        type_="foreignkey",
    )
    op.drop_column("cash_receipts", "waiter_name_snapshot")
    op.drop_column("cash_receipts", "waiter_staff_id")
