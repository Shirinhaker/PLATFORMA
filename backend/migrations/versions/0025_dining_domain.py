"""Ovqatlanish domeni: stollar, ichki zakazlar va zakaz qatorlari.

Zanjir yarim ko'chirilgan edi: zakaz ochish va taom qo'shish JSON yo'lida
ishlagan, lekin oshpazning "tayyor" belgisi va kassirning to'lovi umuman
yo'q edi. Natijada `kitchen_status` hech qachon `done`, `payment_status`
hech qachon `confirmed` bo'lmasdi — stolni bo'shatish sharti esa aynan
shularni talab qiladi, ya'ni stol abadiy band qolardi.

Zakaz — kabinetdagi eng tez o'zgaradigan ma'lumot. JSON blobda saqlansa,
oshpaz, ofitsiantlar va kassir bir vaqtda yozganda bir-birining
o'zgarishini yo'q qiladi. Shu sababli alohida jadvallarga chiqariladi.

Eski ma'lumot yo'qolmaydi: mavjud stollar va ochiq hisoblar kabinet
yozuvlaridan (relatsion V7 store va eski JSON payload) ko'chiriladi.
"""

from alembic import op
import sqlalchemy as sa


revision = "0025_dining_domain"
down_revision = "0024_payments_domain"
branch_labels = None
depends_on = None


# 0018/0024 dagi bilan aynan bir xil — V7 relatsion store'dagi maydon
# qiymatini jsonb'ga aylantiradi.
JSON_VALUE_SQL = r"""
CASE field.value_type
    WHEN 'null' THEN 'null'::jsonb
    WHEN 'boolean' THEN to_jsonb(field.value_boolean)
    WHEN 'integer' THEN to_jsonb(field.value_integer)
    WHEN 'float' THEN to_jsonb(field.value_float)
    ELSE to_jsonb(COALESCE(field.value_text, ''))
END
"""


def _source_rows_sql(resource: str) -> str:
    """Bitta kabinet resursining qatorlarini ikkala manbadan yig'adi.

    V7 relatsion store ustun turadi (`priority = 0`), eski JSON payload
    faqat u yerda yozuv bo'lmasa ishlatiladi.
    """
    return rf"""
relational_rows AS (
    SELECT
        resource.account_id,
        record.source_key,
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
      AND resource.resource = '{resource}'
    GROUP BY resource.account_id, record.id, record.source_key
),
payload_rows AS (
    SELECT
        profile.account_id,
        COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality)
            AS source_key,
        entry.row_data,
        1 AS priority
    FROM business_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(
            COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
            -> '{resource}'
        ) = 'array'
        THEN COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
            -> '{resource}'
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
    ORDER BY account_id, source_key, priority
)
"""


def _int_or(expr: str, default: str) -> str:
    """JSON matnini butun songa aylantiradi, aks holda `default` qaytaradi."""
    return (
        f"COALESCE(CASE WHEN COALESCE({expr}, '') ~ '^-?[0-9]+$' "
        f"THEN ({expr})::bigint END, {default})"
    )


PLACES_BACKFILL_SQL = rf"""
WITH {_source_rows_sql("dining_places")}
INSERT INTO dining_places (
    business_account_id, legacy_source_id, kind, name, seats,
    x, y, locked, created_at, updated_at
)
SELECT
    source.account_id,
    (source.row_data->>'id')::bigint,
    CASE WHEN source.row_data->>'kind' = 'room' THEN 'room' ELSE 'table' END,
    left(COALESCE(NULLIF(source.row_data->>'name', ''), 'Stol'), 120),
    GREATEST(0, {_int_or("source.row_data->>'seats'", "0")})::integer,
    COALESCE(
        CASE WHEN COALESCE(source.row_data->>'x', '') ~ '^-?[0-9.]+$'
            THEN (source.row_data->>'x')::double precision END, 4),
    COALESCE(
        CASE WHEN COALESCE(source.row_data->>'y', '') ~ '^-?[0-9.]+$'
            THEN (source.row_data->>'y')::double precision END, 4),
    COALESCE(
        CASE WHEN source.row_data->>'locked' IN ('0', 'false') THEN false
             WHEN source.row_data->>'locked' IN ('1', 'true') THEN true END,
        true),
    to_timestamp({_int_or("source.row_data->>'created_at'", "EXTRACT(EPOCH FROM now())::bigint")}),
    to_timestamp({_int_or("source.row_data->>'updated_at'", "EXTRACT(EPOCH FROM now())::bigint")})
FROM source_rows AS source
WHERE COALESCE(source.row_data->>'id', '') ~ '^[0-9]+$'
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO NOTHING
"""


ORDERS_BACKFILL_SQL = rf"""
WITH {_source_rows_sql("dining_orders")}
INSERT INTO dining_orders (
    business_account_id, place_id, legacy_source_id, kind,
    customer_name, phone, booking_date, booking_time, guests, note, total,
    waiter_name, problem_open, problem_reason, problem_note,
    problem_opened_at, kitchen_status, payment_status, pay_type,
    status, created_at, updated_at
)
SELECT
    source.account_id,
    place.id,
    (source.row_data->>'id')::bigint,
    CASE WHEN source.row_data->>'kind' = 'booking' THEN 'booking'
         ELSE 'order' END,
    left(COALESCE(source.row_data->>'customer_name', ''), 80),
    left(COALESCE(source.row_data->>'phone', ''), 30),
    left(COALESCE(source.row_data->>'booking_date', ''), 10),
    left(COALESCE(source.row_data->>'booking_time', ''), 5),
    GREATEST(0, {_int_or("source.row_data->>'guests'", "0")})::integer,
    COALESCE(source.row_data->>'note', ''),
    GREATEST(0, {_int_or("source.row_data->>'total'", "0")}),
    left(COALESCE(source.row_data->>'waiter_name', ''), 80),
    COALESCE(source.row_data->>'problem_open' IN ('1', 'true'), false),
    left(COALESCE(source.row_data->>'problem_reason', ''), 80),
    COALESCE(source.row_data->>'problem_note', ''),
    CASE WHEN {_int_or("source.row_data->>'problem_opened_at'", "0")} > 0
        THEN to_timestamp({_int_or("source.row_data->>'problem_opened_at'", "0")})
    END,
    CASE WHEN source.row_data->>'kitchen_status' IN ('new', 'preparing', 'done')
        THEN source.row_data->>'kitchen_status' ELSE 'new' END,
    CASE WHEN source.row_data->>'payment_status' = 'confirmed'
        THEN 'confirmed' ELSE 'open' END,
    CASE WHEN source.row_data->>'pay_type' IN ('naqd', 'karta', 'qarz')
        THEN source.row_data->>'pay_type' ELSE '' END,
    CASE WHEN source.row_data->>'status' IN ('done', 'cancelled')
        THEN source.row_data->>'status' ELSE 'active' END,
    to_timestamp({_int_or("source.row_data->>'created_at'", "EXTRACT(EPOCH FROM now())::bigint")}),
    to_timestamp({_int_or("source.row_data->>'updated_at'", "EXTRACT(EPOCH FROM now())::bigint")})
FROM source_rows AS source
JOIN dining_places AS place
    ON place.business_account_id = source.account_id
   AND place.legacy_source_id
       = {_int_or("source.row_data->>'place_id'", "-1")}
WHERE COALESCE(source.row_data->>'id', '') ~ '^[0-9]+$'
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO NOTHING
"""


# Qatorlar JSON yo'lida zakaz ichida `items` massivi bo'lib turadi
# (v1656da alohida `dining_booking_items` jadvali edi).
ITEMS_BACKFILL_SQL = rf"""
WITH {_source_rows_sql("dining_orders")},
order_items AS (
    SELECT
        source.account_id,
        (source.row_data->>'id')::bigint AS legacy_order_id,
        entry.row_data AS item_data,
        entry.ordinality
    FROM source_rows AS source
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(source.row_data->'items') = 'array'
        THEN source.row_data->'items' ELSE '[]'::jsonb END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
    WHERE COALESCE(source.row_data->>'id', '') ~ '^[0-9]+$'
)
INSERT INTO dining_order_items (
    order_id, business_account_id, catalog_item_id,
    name, qty, unit, price, total, created_at
)
SELECT
    dining_order.id,
    order_items.account_id,
    catalog.id,
    left(COALESCE(NULLIF(order_items.item_data->>'name', ''), 'Taom'), 220),
    GREATEST(0.001, COALESCE(
        CASE WHEN COALESCE(order_items.item_data->>'qty', '') ~ '^[0-9.]+$'
            THEN (order_items.item_data->>'qty')::numeric END, 1))::numeric(15, 3),
    left(COALESCE(NULLIF(order_items.item_data->>'unit', ''), 'dona'), 40),
    GREATEST(0, {_int_or("order_items.item_data->>'price'", "0")}),
    GREATEST(0, {_int_or("order_items.item_data->>'total'", "0")}),
    dining_order.created_at
FROM order_items
JOIN dining_orders AS dining_order
    ON dining_order.business_account_id = order_items.account_id
   AND dining_order.legacy_source_id = order_items.legacy_order_id
LEFT JOIN catalog_items AS catalog
    ON catalog.business_account_id = order_items.account_id
   AND catalog.source_record_key = order_items.item_data->>'item_id'
WHERE NOT EXISTS (
    SELECT 1 FROM dining_order_items AS existing
    WHERE existing.order_id = dining_order.id
)
"""


def upgrade() -> None:
    op.create_table(
        "dining_places",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("seats", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("x", sa.Float(), nullable=False, server_default="4"),
        sa.Column("y", sa.Float(), nullable=False, server_default="4"),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('table', 'room')", name="ck_dining_places_kind"
        ),
        sa.CheckConstraint("seats >= 0", name="ck_dining_places_seats"),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_dining_places_business",
        "dining_places",
        ["business_account_id", "id"],
    )
    op.create_index(
        "uq_dining_places_legacy",
        "dining_places",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
        sqlite_where=sa.text("legacy_source_id IS NOT NULL"),
    )

    op.create_table(
        "dining_orders",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("place_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "customer_name", sa.String(length=80), nullable=False,
            server_default="",
        ),
        sa.Column(
            "phone", sa.String(length=30), nullable=False, server_default=""
        ),
        sa.Column(
            "booking_date", sa.String(length=10), nullable=False,
            server_default="",
        ),
        sa.Column(
            "booking_time", sa.String(length=5), nullable=False,
            server_default="",
        ),
        sa.Column("guests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("total", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("waiter_staff_id", sa.BigInteger()),
        sa.Column(
            "waiter_name", sa.String(length=80), nullable=False,
            server_default="",
        ),
        sa.Column(
            "problem_open", sa.Boolean(), nullable=False, server_default="0"
        ),
        sa.Column(
            "problem_reason", sa.String(length=80), nullable=False,
            server_default="",
        ),
        sa.Column(
            "problem_note", sa.Text(), nullable=False, server_default=""
        ),
        sa.Column("problem_opened_at", sa.DateTime(timezone=True)),
        sa.Column(
            "kitchen_status", sa.String(length=16), nullable=False,
            server_default="new",
        ),
        sa.Column(
            "payment_status", sa.String(length=16), nullable=False,
            server_default="open",
        ),
        sa.Column(
            "pay_type", sa.String(length=16), nullable=False, server_default=""
        ),
        sa.Column("debtor_id", sa.BigInteger()),
        sa.Column("cash_receipt_id", sa.BigInteger()),
        sa.Column(
            "status", sa.String(length=16), nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('order', 'booking')", name="ck_dining_orders_kind"
        ),
        sa.CheckConstraint(
            "kitchen_status IN ('new', 'preparing', 'done')",
            name="ck_dining_orders_kitchen_status",
        ),
        sa.CheckConstraint(
            "payment_status IN ('open', 'confirmed')",
            name="ck_dining_orders_payment_status",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'done', 'cancelled')",
            name="ck_dining_orders_status",
        ),
        sa.CheckConstraint(
            "pay_type IN ('', 'naqd', 'karta', 'qarz')",
            name="ck_dining_orders_pay_type",
        ),
        sa.CheckConstraint("total >= 0", name="ck_dining_orders_total"),
        sa.CheckConstraint("guests >= 0", name="ck_dining_orders_guests"),
        sa.CheckConstraint(
            "pay_type <> 'qarz' OR debtor_id IS NOT NULL",
            name="ck_dining_orders_debt_has_debtor",
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["place_id"], ["dining_places.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["waiter_staff_id"], ["staff_members.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["debtor_id"], ["debtors.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["cash_receipt_id"], ["cash_receipts.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_dining_orders_place",
        "dining_orders",
        ["business_account_id", "place_id", "status", "id"],
    )
    op.create_index(
        "ix_dining_orders_kitchen",
        "dining_orders",
        ["business_account_id", "kitchen_status", "id"],
    )
    op.create_index(
        "ix_dining_orders_cashier",
        "dining_orders",
        ["business_account_id", "payment_status", "problem_open", "id"],
    )
    op.create_index(
        "uq_dining_orders_legacy",
        "dining_orders",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
        sqlite_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "uq_dining_orders_cash_receipt",
        "dining_orders",
        ["cash_receipt_id"],
        unique=True,
        postgresql_where=sa.text("cash_receipt_id IS NOT NULL"),
        sqlite_where=sa.text("cash_receipt_id IS NOT NULL"),
    )

    op.create_table(
        "dining_order_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("catalog_item_id", sa.BigInteger()),
        sa.Column("name", sa.String(length=220), nullable=False),
        sa.Column("qty", sa.Numeric(15, 3), nullable=False),
        sa.Column(
            "unit", sa.String(length=40), nullable=False, server_default="dona"
        ),
        sa.Column("price", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_dining_order_items_qty"),
        sa.CheckConstraint("price >= 0", name="ck_dining_order_items_price"),
        sa.CheckConstraint("total >= 0", name="ck_dining_order_items_total"),
        sa.ForeignKeyConstraint(
            ["order_id"], ["dining_orders.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["catalog_item_id"], ["catalog_items.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_dining_order_items_order",
        "dining_order_items",
        ["order_id", "id"],
    )

    # Eski ma'lumotni ko'chirish faqat PostgreSQL'da (jsonb funksiyalari).
    # SQLite ustidagi testlar bo'sh jadvallardan boshlaydi.
    if op.get_bind().dialect.name != "postgresql":
        return
    # Har bir `op.execute` — bitta bayonot (asyncpg ko'p bayonotni
    # tayyorlangan so'rovda qabul qilmaydi).
    op.execute(PLACES_BACKFILL_SQL)
    op.execute(ORDERS_BACKFILL_SQL)
    op.execute(ITEMS_BACKFILL_SQL)


def downgrade() -> None:
    op.drop_table("dining_order_items")
    op.drop_table("dining_orders")
    op.drop_table("dining_places")
