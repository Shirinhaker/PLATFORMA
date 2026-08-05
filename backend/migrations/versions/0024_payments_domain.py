"""To'lovlar domeni: narxlar, usullar, so'rovlar, cheklar va audit izi.

To'lov oqimi umuman ko'chirilmagan edi — shu sababli obuna sotib olish
tugmasi bosilganda to'lov oynasi ochilmasdi.

Eski so'rovlar kabinet `payment_requests` resursidan ko'chiriladi.
Chek fayllari eski serverning lokal diskida qolgan — ular ko'chirilmaydi,
faqat metama'lumot saqlanadi (`receipt_object_key` bo'sh qoladi).
Yangi cheklar R2'ga yuklanadi.
"""

from alembic import op
import sqlalchemy as sa


revision = "0024_payments_domain"
down_revision = "0023_profile_follows"
branch_labels = None
depends_on = None


# v1656 `payments.py:PRICE_RULES` bilan bir xil.
PRICE_RULES = (
    ("subscription_plus_1m", "subscription", 99_000, "plus", 1, 1),
    ("subscription_plus_3m", "subscription", 279_000, "plus", 3, 1),
    ("subscription_plus_12m", "subscription", 990_000, "plus", 12, 1),
    ("subscription_pro_1m", "subscription", 149_000, "pro", 1, 1),
    ("subscription_pro_3m", "subscription", 419_000, "pro", 3, 1),
    ("subscription_pro_12m", "subscription", 1_490_000, "pro", 12, 1),
    ("advertisement_district_day", "advertisement", 50_000, "", 0, 0),
    ("advertisement_district_hour", "advertisement", 20_000, "", 0, 1),
    ("listing_publish", "listing", 15_000, "", 0, 1),
)


JSON_VALUE_SQL = r"""
CASE field.value_type
    WHEN 'null' THEN 'null'::jsonb
    WHEN 'boolean' THEN to_jsonb(field.value_boolean)
    WHEN 'integer' THEN to_jsonb(field.value_integer)
    WHEN 'float' THEN to_jsonb(field.value_float)
    ELSE to_jsonb(COALESCE(field.value_text, ''))
END
"""


REQUEST_BACKFILL_SQL = rf"""
WITH
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
      AND resource.resource = 'payment_requests'
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
            -> 'payment_requests'
        ) = 'array'
        THEN COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
            -> 'payment_requests'
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
INSERT INTO payment_requests (
    legacy_source_id, request_code, actor_type, account_id, service_type,
    target_id, plan_code, duration_months, quantity, unit_price_snapshot,
    amount_snapshot, currency, price_code, target_snapshot,
    payment_method_id, status, approved_at, rejected_at, cancelled_at,
    public_reason, internal_note, created_at, updated_at
)
SELECT
    CASE WHEN COALESCE(source.row_data->>'id', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'id')::bigint ELSE NULL END,
    COALESCE(
        NULLIF(source.row_data->>'request_code', ''),
        'LEGACY-' || source.account_id || '-' || source.source_key
    ),
    CASE WHEN source.row_data->>'actor_type' = 'user' THEN 'user'
        ELSE 'business' END,
    source.account_id,
    CASE WHEN source.row_data->>'service_type'
            IN ('advertisement', 'subscription', 'listing')
        THEN source.row_data->>'service_type' ELSE 'subscription' END,
    CASE WHEN COALESCE(source.row_data->>'target_id', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'target_id')::bigint ELSE NULL END,
    left(COALESCE(source.row_data->>'plan_code', ''), 32),
    COALESCE(
        CASE WHEN COALESCE(source.row_data->>'duration_months', '') ~ '^[0-9]+$'
            THEN (source.row_data->>'duration_months')::integer END, 0),
    GREATEST(1, COALESCE(
        CASE WHEN COALESCE(source.row_data->>'quantity', '') ~ '^[0-9]+$'
            THEN (source.row_data->>'quantity')::integer END, 1)),
    COALESCE(
        CASE WHEN COALESCE(source.row_data->>'unit_price_snapshot', '') ~ '^[0-9]+$'
            THEN (source.row_data->>'unit_price_snapshot')::bigint END, 0),
    COALESCE(
        CASE WHEN COALESCE(source.row_data->>'amount_snapshot', '') ~ '^[0-9]+$'
            THEN (source.row_data->>'amount_snapshot')::bigint END, 0),
    'UZS',
    left(COALESCE(source.row_data->>'price_code', ''), 64),
    '{{}}'::jsonb,
    1,
    CASE WHEN source.row_data->>'status'
            IN ('pending', 'approved', 'rejected', 'cancelled')
        THEN source.row_data->>'status' ELSE 'pending' END,
    COALESCE(
        CASE WHEN COALESCE(source.row_data->>'approved_at', '') ~ '^[0-9]+$'
            THEN (source.row_data->>'approved_at')::bigint END, 0),
    COALESCE(
        CASE WHEN COALESCE(source.row_data->>'rejected_at', '') ~ '^[0-9]+$'
            THEN (source.row_data->>'rejected_at')::bigint END, 0),
    COALESCE(
        CASE WHEN COALESCE(source.row_data->>'cancelled_at', '') ~ '^[0-9]+$'
            THEN (source.row_data->>'cancelled_at')::bigint END, 0),
    COALESCE(source.row_data->>'public_reason', ''),
    '',
    COALESCE(
        CASE WHEN COALESCE(source.row_data->>'created_at', '') ~ '^[0-9]+$'
            THEN (source.row_data->>'created_at')::bigint END,
        EXTRACT(EPOCH FROM now())::bigint),
    COALESCE(
        CASE WHEN COALESCE(source.row_data->>'updated_at', '') ~ '^[0-9]+$'
            THEN (source.row_data->>'updated_at')::bigint END,
        EXTRACT(EPOCH FROM now())::bigint)
FROM source_rows AS source
WHERE COALESCE(source.row_data->>'id', '') ~ '^[0-9]+$'
ON CONFLICT (legacy_source_id) WHERE legacy_source_id IS NOT NULL
DO NOTHING
"""


def upgrade() -> None:
    op.create_table(
        "platform_prices",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("price_code", sa.String(length=64), nullable=False),
        sa.Column("amount_uzs", sa.BigInteger(), nullable=False),
        sa.Column(
            "service_type", sa.String(length=32), nullable=False, server_default=""
        ),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("amount_uzs >= 0", name="ck_platform_prices_amount"),
        sa.UniqueConstraint("price_code", name="uq_platform_prices_code"),
    )
    op.create_table(
        "payment_methods",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("method_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "recipient_name", sa.String(length=160), nullable=False, server_default=""
        ),
        sa.Column("instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
    )
    op.create_table(
        "payment_requests",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("request_code", sa.String(length=40), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("service_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.BigInteger()),
        sa.Column("plan_code", sa.String(length=32), nullable=False, server_default=""),
        sa.Column(
            "duration_months", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price_snapshot", sa.BigInteger(), nullable=False),
        sa.Column("amount_snapshot", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="UZS"),
        sa.Column("price_code", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("target_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("payment_method_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("reviewed_by_account_id", sa.BigInteger()),
        sa.Column("approved_at", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rejected_at", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cancelled_at", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("public_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("internal_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('user', 'business')",
            name="ck_payment_requests_actor_type",
        ),
        sa.CheckConstraint(
            "service_type IN ('advertisement', 'subscription', 'listing')",
            name="ck_payment_requests_service_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_payment_requests_status",
        ),
        sa.CheckConstraint(
            "amount_snapshot >= 0", name="ck_payment_requests_amount"
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["payment_method_id"], ["payment_methods.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("request_code", name="uq_payment_requests_code"),
    )
    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("payment_request_id", sa.BigInteger(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("receipt_object_key", sa.String(length=1024), nullable=False),
        sa.Column(
            "receipt_filename", sa.String(length=255), nullable=False, server_default=""
        ),
        sa.Column("receipt_mime", sa.String(length=120), nullable=False),
        sa.Column("receipt_sha256", sa.String(length=64), nullable=False),
        sa.Column("submitted_at", sa.BigInteger(), nullable=False),
        sa.Column("reviewed_at", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "review_status", sa.String(length=16), nullable=False, server_default="pending"
        ),
        sa.Column("review_reason", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected', 'superseded')",
            name="ck_payment_attempts_review_status",
        ),
        sa.ForeignKeyConstraint(
            ["payment_request_id"], ["payment_requests.id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "payment_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("payment_request_id", sa.BigInteger(), nullable=False),
        sa.Column("from_status", sa.String(length=16), nullable=False),
        sa.Column("to_status", sa.String(length=16), nullable=False),
        sa.Column("actor_kind", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["payment_request_id"], ["payment_requests.id"], ondelete="CASCADE"
        ),
    )

    op.create_table(
        "business_subscriptions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("plan_code", sa.String(length=16), nullable=False),
        sa.Column("duration_months", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("is_demo", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payment_request_id", sa.BigInteger()),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "plan_code IN ('plus', 'pro')",
            name="ck_business_subscriptions_plan",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'superseded', 'expired')",
            name="ck_business_subscriptions_status",
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["payment_request_id"], ["payment_requests.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_business_subscriptions_active",
        "business_subscriptions",
        ["business_account_id", "status", "expires_at"],
    )
    op.create_index(
        "uq_business_subscriptions_payment",
        "business_subscriptions",
        ["payment_request_id"],
        unique=True,
        postgresql_where=sa.text("payment_request_id IS NOT NULL"),
    )

    op.create_index(
        "ix_payment_requests_owner",
        "payment_requests",
        ["account_id", "actor_type", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_payment_requests_status",
        "payment_requests",
        ["status", "created_at", "id"],
    )
    op.create_index(
        "uq_payment_requests_legacy",
        "payment_requests",
        ["legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "uq_payment_attempts_no",
        "payment_attempts",
        ["payment_request_id", "attempt_no"],
        unique=True,
    )
    op.create_index(
        "ix_payment_attempts_receipt_hash",
        "payment_attempts",
        ["receipt_sha256"],
    )
    op.create_index(
        "ix_payment_events_request",
        "payment_events",
        ["payment_request_id", "id"],
    )

    op.execute(
        "INSERT INTO payment_methods ("
        "  id, method_type, name, details, recipient_name, instructions,"
        "  sort_order, active, created_at, updated_at"
        ") VALUES ("
        "  1, 'manual_card', 'Bank kartasi', '{}', '', '', 0, 1,"
        "  EXTRACT(EPOCH FROM now())::bigint,"
        "  EXTRACT(EPOCH FROM now())::bigint"
        ")"
    )
    for code, service, amount, plan, months, active in PRICE_RULES:
        config = (
            f"""'{{"plan_code": "{plan}", "duration_months": {months}}}'"""
            if service == "subscription"
            else "'{}'"
        )
        op.execute(
            "INSERT INTO platform_prices ("
            "  price_code, amount_uzs, service_type, config, active,"
            "  created_at, updated_at"
            f") VALUES ('{code}', {amount}, '{service}', {config}::jsonb,"
            f" {active},"
            "  EXTRACT(EPOCH FROM now())::bigint,"
            "  EXTRACT(EPOCH FROM now())::bigint"
            ") ON CONFLICT (price_code) DO NOTHING"
        )
    op.execute(REQUEST_BACKFILL_SQL)


def downgrade() -> None:
    op.drop_table("business_subscriptions")
    op.drop_table("payment_events")
    op.drop_table("payment_attempts")
    op.drop_table("payment_requests")
    op.drop_table("payment_methods")
    op.drop_table("platform_prices")
