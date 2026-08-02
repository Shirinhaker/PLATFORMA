"""Buyurtmalarni v1656 oqimi bilan jonli ishlaydigan holatga o'tkazish.

Revision ID: 0009_orders_live_v1656
Revises: 0008_listings_live_v1656
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_orders_live_v1656"
down_revision = "0008_listings_live_v1656"
branch_labels = None
depends_on = None


# Relatsion kabinet yozuvlari root maydonlar uchun birinchi manba, eski JSON esa
# ichki items/messages massivlari va relatsionlashmagan akkauntlar uchun fallback.
ORDER_SOURCE_CTES = r"""
relational_order_rows AS (
    SELECT
        resource.account_id AS snapshot_account_id,
        resource.account_type::text AS snapshot_account_type,
        record.source_key,
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
    WHERE resource.resource = 'orders'
    GROUP BY resource.account_id, resource.account_type, record.id, record.source_key
),
payload_order_rows AS (
    SELECT
        profile.account_id AS snapshot_account_id,
        'user'::text AS snapshot_account_type,
        COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality) AS source_key,
        entry.row_data,
        1 AS priority
    FROM user_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'orders') = 'array'
             THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'orders'
             ELSE '[]'::jsonb END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
    UNION ALL
    SELECT
        profile.account_id,
        'business'::text,
        COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality),
        entry.row_data,
        1
    FROM business_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'orders') = 'array'
             THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'orders'
             ELSE '[]'::jsonb END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
),
all_order_rows AS (
    SELECT * FROM relational_order_rows
    UNION ALL
    SELECT * FROM payload_order_rows
),
order_source AS (
    SELECT DISTINCT ON (COALESCE(NULLIF(row_data->>'id', ''), source_key)::bigint)
        COALESCE(NULLIF(row_data->>'id', ''), source_key)::bigint AS legacy_source_id,
        row_data
    FROM all_order_rows
    WHERE COALESCE(row_data->>'id', source_key, '') ~ '^[0-9]+$'
      AND COALESCE(row_data->>'customer_kind', '') IN ('user', 'business')
      AND COALESCE(row_data->>'provider_kind', '') IN ('user', 'business')
    ORDER BY COALESCE(NULLIF(row_data->>'id', ''), source_key)::bigint,
             priority, snapshot_account_type
)
"""


NESTED_SOURCE_CTES = r"""
payload_orders AS (
    SELECT entry.row_data
    FROM user_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'orders') = 'array'
             THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'orders'
             ELSE '[]'::jsonb END
    ) AS entry(row_data)
    UNION ALL
    SELECT entry.row_data
    FROM business_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'orders') = 'array'
             THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'orders'
             ELSE '[]'::jsonb END
    ) AS entry(row_data)
),
unique_payload_orders AS (
    SELECT DISTINCT ON ((row_data->>'id')::bigint) row_data
    FROM payload_orders
    WHERE COALESCE(row_data->>'id', '') ~ '^[0-9]+$'
    ORDER BY (row_data->>'id')::bigint
)
"""


def upgrade() -> None:
    op.add_column(
        "catalog_items",
        sa.Column("unit", sa.String(length=40), nullable=False, server_default="dona"),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("customer_account_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_kind", sa.String(length=20), nullable=False),
        sa.Column("customer_name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("customer_phone", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("provider_account_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_kind", sa.String(length=20), nullable=False),
        sa.Column("provider_name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("provider_phone", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("item_id", sa.BigInteger()),
        sa.Column("listing_id", sa.BigInteger()),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("note", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("order_type", sa.String(length=20), nullable=False),
        sa.Column("order_category", sa.String(length=20), nullable=False, server_default="product"),
        sa.Column("address", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("desired_time", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("delivery_lat", sa.Float()),
        sa.Column("delivery_lng", sa.Float()),
        sa.Column("qty", sa.Numeric(12, 3), nullable=False, server_default="1"),
        sa.Column("total_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("payment_status", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("pay_type", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("receipt_message_id", sa.BigInteger()),
        sa.Column("problem_open", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("problem_reason", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("problem_note", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("problem_solution", sa.String(length=30), nullable=False, server_default=""),
        sa.Column("problem_opened_at", sa.DateTime(timezone=True)),
        sa.Column("problem_resolved_at", sa.DateTime(timezone=True)),
        sa.Column("last_event", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("customer_seen_at", sa.DateTime(timezone=True)),
        sa.Column("provider_seen_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("ready_at", sa.DateTime(timezone=True)),
        sa.Column("handed_off_at", sa.DateTime(timezone=True)),
        sa.Column("seller_completed_at", sa.DateTime(timezone=True)),
        sa.Column("customer_received_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["provider_account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["item_id"], ["catalog_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("legacy_source_id", name="uq_orders_legacy_source_id"),
        sa.CheckConstraint("customer_kind IN ('user', 'business')", name="ck_orders_customer_kind"),
        sa.CheckConstraint("provider_kind IN ('user', 'business')", name="ck_orders_provider_kind"),
        sa.CheckConstraint("order_type IN ('delivery', 'pickup', 'booking')", name="ck_orders_order_type"),
        sa.CheckConstraint(
            "status IN ('new', 'accepted', 'rejected', 'preparing', 'tayyor', 'cancelled', "
            "'courier_assigned', 'courier_arrived_store', 'handoff_waiting_seller', "
            "'in_delivery', 'courier_arrived_customer', 'pickup_waiting_customer', "
            "'delivered_waiting_customer', 'done')",
            name="ck_orders_status",
        ),
        sa.CheckConstraint(
            "payment_status IN ('', 'pending', 'submitted', 'recheck', 'disputed', 'confirmed', 'rejected')",
            name="ck_orders_payment_status",
        ),
        sa.CheckConstraint("qty > 0", name="ck_orders_qty"),
        sa.CheckConstraint("total_amount >= 0", name="ck_orders_total_amount"),
        sa.CheckConstraint(
            "order_category IN ('product', 'service')",
            name="ck_orders_order_category",
        ),
        sa.CheckConstraint(
            "delivery_lat IS NULL OR delivery_lat BETWEEN -90 AND 90",
            name="ck_orders_delivery_lat",
        ),
        sa.CheckConstraint(
            "delivery_lng IS NULL OR delivery_lng BETWEEN -180 AND 180",
            name="ck_orders_delivery_lng",
        ),
        sa.CheckConstraint(
            "problem_solution IN ('', 'pickup', 'wait', 'new_receipt')",
            name="ck_orders_problem_solution",
        ),
    )
    op.create_index("ix_orders_customer_created", "orders", ["customer_account_id", "created_at"])
    op.create_index("ix_orders_provider_created", "orders", ["provider_account_id", "created_at"])
    op.create_index(
        "ix_orders_provider_unread", "orders", ["provider_account_id", "updated_at"],
        postgresql_where=sa.text("provider_seen_at IS NULL"),
    )
    op.create_index(
        "ix_orders_customer_unread", "orders", ["customer_account_id", "updated_at"],
        postgresql_where=sa.text("customer_seen_at IS NULL"),
    )
    op.create_index("ix_orders_item_id", "orders", ["item_id"])
    op.create_index("ix_orders_listing_id", "orders", ["listing_id"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("catalog_item_id", sa.BigInteger()),
        sa.Column("item_name", sa.String(length=180), nullable=False),
        sa.Column("price_text", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("qty", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False, server_default="dona"),
        sa.Column("line_total", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("note", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="product"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["catalog_item_id"], ["catalog_items.id"], ondelete="SET NULL"),
        sa.CheckConstraint("qty > 0", name="ck_order_items_qty"),
        sa.CheckConstraint("line_total >= 0", name="ck_order_items_line_total"),
        sa.CheckConstraint("kind IN ('product', 'service')", name="ck_order_items_kind"),
    )
    op.create_index("ix_order_items_order", "order_items", ["order_id", "id"])
    op.create_index("ix_order_items_catalog_item", "order_items", ["catalog_item_id"])
    op.create_index(
        "uq_order_items_legacy", "order_items", ["order_id", "legacy_source_id"],
        unique=True, postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )

    op.create_table(
        "order_messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("sender_account_id", sa.BigInteger(), nullable=False),
        sa.Column("sender_kind", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("media_type", sa.String(length=20), nullable=False, server_default="text"),
        sa.Column("media_object_key", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("legacy_media_url", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("file_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("reply_to_id", sa.BigInteger()),
        sa.Column("edited_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reply_to_id"], ["order_messages.id"], ondelete="SET NULL"),
        sa.CheckConstraint("sender_kind IN ('user', 'business')", name="ck_order_messages_sender_kind"),
        sa.CheckConstraint("media_type IN ('text', 'photo')", name="ck_order_messages_media_type"),
    )
    op.create_index(
        "ix_order_messages_order_created", "order_messages", ["order_id", "created_at", "id"]
    )
    op.create_index(
        "ix_order_messages_sender", "order_messages", ["sender_account_id", "created_at"]
    )
    op.create_index("ix_order_messages_reply_to", "order_messages", ["reply_to_id"])
    op.create_index(
        "uq_order_messages_legacy", "order_messages", ["order_id", "legacy_source_id"],
        unique=True, postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )

    # Mahsulot birligini eski kabinetdan jonli katalogga olib o'tamiz.
    op.execute(sa.text(r"""
        UPDATE catalog_items AS target
        SET unit = left(COALESCE(NULLIF(trim(field.value_text), ''), 'dona'), 40)
        FROM cabinet_resources AS resource
        JOIN cabinet_records AS record ON record.resource_id = resource.id
        JOIN cabinet_record_fields AS field ON field.record_id = record.id AND field.path = '/unit'
        WHERE resource.account_type = 'business'
          AND resource.resource = 'items'
          AND target.business_account_id = resource.account_id
          AND target.source_record_key = record.source_key
    """))

    # Bitta legacy buyurtma mijoz va sotuvchi snapshotlarida takrorlangan bo'lishi
    # mumkin; DISTINCT ON va unique legacy_source_id uni bir marta yozadi.
    op.execute(sa.text(f"""
        WITH {ORDER_SOURCE_CTES}, mapped AS (
            SELECT source.*,
                   customer_map.target_id AS customer_account_id,
                   provider_map.target_id AS provider_account_id,
                   item_map.target_id AS item_id,
                   listing_map.target_id AS listing_id
            FROM order_source AS source
            JOIN legacy_id_map AS customer_map
              ON customer_map.entity_type = CASE source.row_data->>'customer_kind'
                    WHEN 'business' THEN 'business_account' ELSE 'user_account' END
             AND customer_map.legacy_id = CASE
                    WHEN COALESCE(source.row_data->>'customer_actor_id', '') ~ '^[0-9]+$'
                    THEN (source.row_data->>'customer_actor_id')::bigint ELSE NULL END
            JOIN legacy_id_map AS provider_map
              ON provider_map.entity_type = CASE source.row_data->>'provider_kind'
                    WHEN 'business' THEN 'business_account' ELSE 'user_account' END
             AND provider_map.legacy_id = CASE
                    WHEN COALESCE(source.row_data->>'provider_actor_id', '') ~ '^[0-9]+$'
                    THEN (source.row_data->>'provider_actor_id')::bigint ELSE NULL END
            LEFT JOIN legacy_id_map AS item_map
              ON item_map.entity_type = 'catalog_item'
             AND item_map.legacy_id = CASE WHEN COALESCE(source.row_data->>'item_id', '') ~ '^[0-9]+$'
                    THEN (source.row_data->>'item_id')::bigint ELSE NULL END
            LEFT JOIN legacy_id_map AS listing_map
              ON listing_map.entity_type = 'listing'
             AND listing_map.legacy_id = CASE WHEN COALESCE(source.row_data->>'listing_id', '') ~ '^[0-9]+$'
                    THEN (source.row_data->>'listing_id')::bigint ELSE NULL END
            WHERE customer_map.target_id IS NOT NULL AND provider_map.target_id IS NOT NULL
        )
        INSERT INTO orders (
            legacy_source_id, customer_account_id, customer_kind, customer_name,
            customer_phone, provider_account_id, provider_kind, provider_name,
            provider_phone, item_id, listing_id, title, note, phone, order_type,
            order_category, address, desired_time, delivery_lat, delivery_lng, qty,
            total_amount, status, payment_status, pay_type, receipt_message_id,
            problem_open, problem_reason, problem_note, problem_solution, last_event,
            problem_opened_at, problem_resolved_at,
            customer_seen_at, provider_seen_at, accepted_at, ready_at, handed_off_at,
            seller_completed_at,
            customer_received_at, created_at, updated_at
        )
        SELECT
            mapped.legacy_source_id, mapped.customer_account_id,
            mapped.row_data->>'customer_kind',
            left(COALESCE(customer_business.name, customer_user.name, ''), 160),
            left(COALESCE(customer_business.phone, customer_user.phone, ''), 32),
            mapped.provider_account_id, mapped.row_data->>'provider_kind',
            left(COALESCE(provider_business.name, provider_user.name, ''), 160),
            left(COALESCE(provider_business.phone, provider_user.phone, ''), 32),
            mapped.item_id, mapped.listing_id,
            left(COALESCE(NULLIF(trim(mapped.row_data->>'title'), ''), 'Buyurtma'), 180),
            left(COALESCE(mapped.row_data->>'note', ''), 1000),
            left(COALESCE(mapped.row_data->>'phone', ''), 80),
            CASE WHEN mapped.row_data->>'order_type' IN ('delivery', 'pickup', 'booking')
                 THEN mapped.row_data->>'order_type' ELSE 'delivery' END,
            CASE WHEN mapped.row_data->>'order_category' IN ('product', 'service')
                 THEN mapped.row_data->>'order_category'
                 WHEN mapped.row_data->>'order_type' = 'booking' THEN 'service' ELSE 'product' END,
            left(COALESCE(mapped.row_data->>'address', ''), 500),
            left(COALESCE(mapped.row_data->>'desired_time', ''), 160),
            CASE WHEN COALESCE(mapped.row_data->>'delivery_lat', '') ~ '^-?[0-9]+([.][0-9]+)?$'
                 THEN (mapped.row_data->>'delivery_lat')::double precision ELSE NULL END,
            CASE WHEN COALESCE(mapped.row_data->>'delivery_lng', '') ~ '^-?[0-9]+([.][0-9]+)?$'
                 THEN (mapped.row_data->>'delivery_lng')::double precision ELSE NULL END,
            CASE WHEN COALESCE(mapped.row_data->>'qty', '') ~ '^[0-9]+([.][0-9]+)?$'
                 AND (mapped.row_data->>'qty')::numeric > 0
                 THEN LEAST((mapped.row_data->>'qty')::numeric, 999) ELSE 1 END,
            CASE WHEN COALESCE(mapped.row_data->>'total_amount', mapped.row_data->>'total', '') ~ '^[0-9]+$'
                 THEN COALESCE(mapped.row_data->>'total_amount', mapped.row_data->>'total')::bigint ELSE 0 END,
            CASE WHEN mapped.row_data->>'status' IN (
                    'new', 'accepted', 'rejected', 'preparing', 'tayyor', 'cancelled',
                    'courier_assigned', 'courier_arrived_store', 'handoff_waiting_seller',
                    'in_delivery', 'courier_arrived_customer', 'pickup_waiting_customer',
                    'delivered_waiting_customer', 'done'
                 ) THEN mapped.row_data->>'status' ELSE 'new' END,
            CASE WHEN COALESCE(mapped.row_data->>'payment_status', '') IN (
                    '', 'pending', 'submitted', 'recheck', 'disputed', 'confirmed', 'rejected'
                 ) THEN COALESCE(mapped.row_data->>'payment_status', '') ELSE '' END,
            left(COALESCE(mapped.row_data->>'pay_type', ''), 20), NULL,
            lower(COALESCE(mapped.row_data->>'problem_open', '')) IN ('1', 'true', 'yes', 'on'),
            left(COALESCE(mapped.row_data->>'problem_reason', ''), 40),
            left(COALESCE(mapped.row_data->>'problem_note', ''), 1000),
            CASE WHEN mapped.row_data->>'problem_solution' IN ('pickup', 'wait', 'new_receipt')
                 THEN mapped.row_data->>'problem_solution' ELSE '' END,
            left(COALESCE(mapped.row_data->>'last_event', ''), 80),
            CASE WHEN COALESCE(mapped.row_data->>'problem_opened_at', '') ~ '^[0-9]+([.][0-9]+)?$'
                       AND (mapped.row_data->>'problem_opened_at')::double precision > 0
                 THEN to_timestamp((mapped.row_data->>'problem_opened_at')::double precision) ELSE NULL END,
            CASE WHEN COALESCE(mapped.row_data->>'problem_resolved_at', '') ~ '^[0-9]+([.][0-9]+)?$'
                       AND (mapped.row_data->>'problem_resolved_at')::double precision > 0
                 THEN to_timestamp((mapped.row_data->>'problem_resolved_at')::double precision) ELSE NULL END,
            CASE WHEN COALESCE(mapped.row_data->>'customer_seen_at', '') ~ '^[0-9]+([.][0-9]+)?$'
                       AND (mapped.row_data->>'customer_seen_at')::double precision > 0
                 THEN to_timestamp((mapped.row_data->>'customer_seen_at')::double precision) ELSE NULL END,
            CASE WHEN COALESCE(mapped.row_data->>'provider_seen_at', '') ~ '^[0-9]+([.][0-9]+)?$'
                       AND (mapped.row_data->>'provider_seen_at')::double precision > 0
                 THEN to_timestamp((mapped.row_data->>'provider_seen_at')::double precision) ELSE NULL END,
            NULL, NULL, NULL,
            CASE WHEN COALESCE(mapped.row_data->>'seller_completed_at', '') ~ '^[0-9]+([.][0-9]+)?$'
                       AND (mapped.row_data->>'seller_completed_at')::double precision > 0
                 THEN to_timestamp((mapped.row_data->>'seller_completed_at')::double precision) ELSE NULL END,
            CASE WHEN COALESCE(mapped.row_data->>'customer_received_at', '') ~ '^[0-9]+([.][0-9]+)?$'
                       AND (mapped.row_data->>'customer_received_at')::double precision > 0
                 THEN to_timestamp((mapped.row_data->>'customer_received_at')::double precision) ELSE NULL END,
            CASE WHEN COALESCE(mapped.row_data->>'created_at', '') ~ '^[0-9]+([.][0-9]+)?$'
                 THEN to_timestamp((mapped.row_data->>'created_at')::double precision) ELSE now() END,
            CASE WHEN COALESCE(mapped.row_data->>'updated_at', '') ~ '^[0-9]+([.][0-9]+)?$'
                 THEN to_timestamp((mapped.row_data->>'updated_at')::double precision) ELSE now() END
        FROM mapped
        LEFT JOIN user_profiles AS customer_user
          ON mapped.row_data->>'customer_kind' = 'user'
         AND customer_user.account_id = mapped.customer_account_id
        LEFT JOIN business_profiles AS customer_business
          ON mapped.row_data->>'customer_kind' = 'business'
         AND customer_business.account_id = mapped.customer_account_id
        LEFT JOIN user_profiles AS provider_user
          ON mapped.row_data->>'provider_kind' = 'user'
         AND provider_user.account_id = mapped.provider_account_id
        LEFT JOIN business_profiles AS provider_business
          ON mapped.row_data->>'provider_kind' = 'business'
         AND provider_business.account_id = mapped.provider_account_id
        ON CONFLICT (legacy_source_id) DO UPDATE SET
            status = EXCLUDED.status,
            payment_status = EXCLUDED.payment_status,
            problem_open = EXCLUDED.problem_open,
            problem_reason = EXCLUDED.problem_reason,
            problem_note = EXCLUDED.problem_note,
            problem_solution = EXCLUDED.problem_solution,
            customer_seen_at = EXCLUDED.customer_seen_at,
            provider_seen_at = EXCLUDED.provider_seen_at,
            updated_at = EXCLUDED.updated_at
    """))

    op.execute(sa.text(f"""
        WITH {NESTED_SOURCE_CTES}, item_source AS (
            SELECT
                (parent.row_data->>'id')::bigint AS order_legacy_id,
                item.row_data,
                item.ordinality,
                CASE WHEN COALESCE(item.row_data->>'id', '') ~ '^[0-9]+$'
                     THEN (item.row_data->>'id')::bigint ELSE NULL END AS legacy_source_id
            FROM unique_payload_orders AS parent
            CROSS JOIN LATERAL jsonb_array_elements(
                CASE WHEN jsonb_typeof(parent.row_data->'items') = 'array'
                     THEN parent.row_data->'items' ELSE '[]'::jsonb END
            ) WITH ORDINALITY AS item(row_data, ordinality)
        )
        INSERT INTO order_items (
            order_id, legacy_source_id, catalog_item_id, item_name, price_text,
            qty, unit, line_total, note, kind, created_at
        )
        SELECT
            target.id, source.legacy_source_id, item_map.target_id,
            left(COALESCE(NULLIF(source.row_data->>'item_name', ''), source.row_data->>'name', 'Mahsulot/xizmat'), 180),
            left(COALESCE(source.row_data->>'price_text', source.row_data->>'price', ''), 120),
            CASE WHEN COALESCE(source.row_data->>'qty', '') ~ '^[0-9]+([.][0-9]+)?$'
                       AND (source.row_data->>'qty')::numeric > 0
                 THEN LEAST((source.row_data->>'qty')::numeric, 999) ELSE 1 END,
            left(COALESCE(NULLIF(source.row_data->>'unit', ''), 'dona'), 40),
            CASE WHEN COALESCE(source.row_data->>'line_total', '') ~ '^[0-9]+$'
                 THEN (source.row_data->>'line_total')::bigint ELSE 0 END,
            left(COALESCE(source.row_data->>'note', ''), 2000),
            CASE WHEN source.row_data->>'kind' = 'service' THEN 'service' ELSE 'product' END,
            target.created_at
        FROM item_source AS source
        JOIN orders AS target ON target.legacy_source_id = source.order_legacy_id
        LEFT JOIN legacy_id_map AS item_map
          ON item_map.entity_type = 'catalog_item'
         AND item_map.legacy_id = CASE WHEN COALESCE(source.row_data->>'item_id', '') ~ '^[0-9]+$'
                THEN (source.row_data->>'item_id')::bigint ELSE NULL END
        WHERE source.legacy_source_id IS NOT NULL
        ON CONFLICT (order_id, legacy_source_id) WHERE legacy_source_id IS NOT NULL DO UPDATE SET
            catalog_item_id = EXCLUDED.catalog_item_id,
            item_name = EXCLUDED.item_name,
            price_text = EXCLUDED.price_text,
            qty = EXCLUDED.qty,
            unit = EXCLUDED.unit,
            line_total = EXCLUDED.line_total,
            note = EXCLUDED.note,
            kind = EXCLUDED.kind
    """))

    op.execute(sa.text(r"""
        UPDATE orders AS target
        SET total_amount = totals.total_amount,
            qty = totals.total_qty,
            order_category = CASE
                WHEN totals.item_count = totals.service_count THEN 'service'
                ELSE 'product'
            END
        FROM (
            SELECT order_id,
                   COALESCE(SUM(line_total), 0)::bigint AS total_amount,
                   COALESCE(SUM(qty), 1)::numeric(12, 3) AS total_qty,
                   COUNT(*) AS item_count,
                   COUNT(*) FILTER (WHERE kind = 'service') AS service_count
            FROM order_items
            GROUP BY order_id
        ) AS totals
        WHERE target.id = totals.order_id
    """))

    op.execute(sa.text(f"""
        WITH {NESTED_SOURCE_CTES}, message_source AS (
            SELECT
                (parent.row_data->>'id')::bigint AS order_legacy_id,
                message.row_data,
                CASE WHEN COALESCE(message.row_data->>'id', '') ~ '^[0-9]+$'
                     THEN (message.row_data->>'id')::bigint ELSE NULL END AS legacy_source_id
            FROM unique_payload_orders AS parent
            CROSS JOIN LATERAL jsonb_array_elements(
                CASE WHEN jsonb_typeof(parent.row_data->'messages') = 'array'
                     THEN parent.row_data->'messages' ELSE '[]'::jsonb END
            ) AS message(row_data)
        )
        INSERT INTO order_messages (
            legacy_source_id, order_id, sender_account_id, sender_kind, text,
            media_type, media_object_key, legacy_media_url, file_name, reply_to_id,
            edited_at, deleted_at, is_deleted, created_at
        )
        SELECT
            source.legacy_source_id, target.id, sender_map.target_id,
            CASE WHEN source.row_data->>'sender_kind' = 'business' THEN 'business' ELSE 'user' END,
            left(COALESCE(source.row_data->>'text', ''), 2000),
            CASE WHEN source.row_data->>'media_type' = 'photo' THEN 'photo' ELSE 'text' END,
            left(COALESCE(source.row_data->>'media_object_key', ''), 1024),
            left(COALESCE(source.row_data->>'media_url', ''), 2048),
            left(COALESCE(source.row_data->>'file_name', ''), 255),
            NULL,
            CASE WHEN COALESCE(source.row_data->>'edited_at', '') ~ '^[0-9]+([.][0-9]+)?$'
                       AND (source.row_data->>'edited_at')::double precision > 0
                 THEN to_timestamp((source.row_data->>'edited_at')::double precision) ELSE NULL END,
            CASE WHEN COALESCE(source.row_data->>'deleted_at', '') ~ '^[0-9]+([.][0-9]+)?$'
                       AND (source.row_data->>'deleted_at')::double precision > 0
                 THEN to_timestamp((source.row_data->>'deleted_at')::double precision) ELSE NULL END,
            lower(COALESCE(source.row_data->>'is_deleted', '')) IN ('1', 'true', 'yes', 'on'),
            CASE WHEN COALESCE(source.row_data->>'created_at', '') ~ '^[0-9]+([.][0-9]+)?$'
                 THEN to_timestamp((source.row_data->>'created_at')::double precision) ELSE target.created_at END
        FROM message_source AS source
        JOIN orders AS target ON target.legacy_source_id = source.order_legacy_id
        JOIN legacy_id_map AS sender_map
          ON sender_map.entity_type = CASE source.row_data->>'sender_kind'
                WHEN 'business' THEN 'business_account' ELSE 'user_account' END
         AND sender_map.legacy_id = CASE WHEN COALESCE(source.row_data->>'sender_actor_id', '') ~ '^[0-9]+$'
                THEN (source.row_data->>'sender_actor_id')::bigint ELSE NULL END
        WHERE sender_map.target_id IS NOT NULL
          AND source.legacy_source_id IS NOT NULL
        ON CONFLICT (order_id, legacy_source_id) WHERE legacy_source_id IS NOT NULL DO NOTHING
    """))

    # Reply havolalari faqat barcha xabarlar yozilgandan keyin bog'lanadi.
    op.execute(sa.text(f"""
        WITH {NESTED_SOURCE_CTES}, reply_source AS (
            SELECT
                (parent.row_data->>'id')::bigint AS order_legacy_id,
                (message.row_data->>'id')::bigint AS message_legacy_id,
                (message.row_data->>'reply_to_id')::bigint AS reply_legacy_id
            FROM unique_payload_orders AS parent
            CROSS JOIN LATERAL jsonb_array_elements(
                CASE WHEN jsonb_typeof(parent.row_data->'messages') = 'array'
                     THEN parent.row_data->'messages' ELSE '[]'::jsonb END
            ) AS message(row_data)
            WHERE COALESCE(message.row_data->>'id', '') ~ '^[0-9]+$'
              AND COALESCE(message.row_data->>'reply_to_id', '') ~ '^[0-9]+$'
        )
        UPDATE order_messages AS message
        SET reply_to_id = replied.id
        FROM reply_source AS source
        JOIN orders AS target ON target.legacy_source_id = source.order_legacy_id
        JOIN order_messages AS replied
          ON replied.order_id = target.id
         AND replied.legacy_source_id = source.reply_legacy_id
        WHERE message.order_id = target.id
          AND message.legacy_source_id = source.message_legacy_id
    """))


def downgrade() -> None:
    op.drop_index("uq_order_messages_legacy", table_name="order_messages")
    op.drop_index("ix_order_messages_reply_to", table_name="order_messages")
    op.drop_index("ix_order_messages_sender", table_name="order_messages")
    op.drop_index("ix_order_messages_order_created", table_name="order_messages")
    op.drop_table("order_messages")
    op.drop_index("uq_order_items_legacy", table_name="order_items")
    op.drop_index("ix_order_items_catalog_item", table_name="order_items")
    op.drop_index("ix_order_items_order", table_name="order_items")
    op.drop_table("order_items")
    op.drop_index("ix_orders_listing_id", table_name="orders")
    op.drop_index("ix_orders_item_id", table_name="orders")
    op.drop_index("ix_orders_customer_unread", table_name="orders")
    op.drop_index("ix_orders_provider_unread", table_name="orders")
    op.drop_index("ix_orders_provider_created", table_name="orders")
    op.drop_index("ix_orders_customer_created", table_name="orders")
    op.drop_table("orders")
    op.drop_column("catalog_items", "unit")
