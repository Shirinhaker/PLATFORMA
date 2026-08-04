"""Qarz daftari, Kassa va Buyurtma qarz bog'lanishini ko'chirish.

Revision ID: 0017_debt_ledger_domain
Revises: 0016_cash_register_domain
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_debt_ledger_domain"
down_revision = "0016_cash_register_domain"
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


def _source_ctes(resources: tuple[str, ...]) -> str:
    values = ", ".join(f"('{resource}')" for resource in resources)
    names = ", ".join(f"'{resource}'" for resource in resources)
    return rf"""WITH
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
      AND resource.resource IN ({names})
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
    CROSS JOIN LATERAL (VALUES {values}) AS resource_name(resource)
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
    SELECT DISTINCT ON (account_id, resource, source_key)
        account_id, resource, source_key, ordinal, row_data
    FROM (
        SELECT * FROM relational_rows
        UNION ALL
        SELECT * FROM payload_rows
    ) AS candidates
    ORDER BY account_id, resource, source_key, priority, ordinal
)
"""


DEBTOR_BACKFILL_SQL = _source_ctes(("debtors",)) + r"""
INSERT INTO debtors (
    business_account_id, legacy_source_id, name, phone, note, due,
    created_by_staff_id, created_at, updated_at
)
SELECT
    source.account_id,
    CASE WHEN COALESCE(source.row_data->>'id', source.source_key, '') ~ '^[0-9]+$'
        THEN COALESCE(source.row_data->>'id', source.source_key)::bigint
        ELSE NULL END,
    left(COALESCE(NULLIF(trim(source.row_data->>'name'), ''), 'Qarzdor'), 160),
    left(COALESCE(source.row_data->>'phone', ''), 40),
    left(COALESCE(source.row_data->>'note', ''), 200),
    left(COALESCE(source.row_data->>'due', ''), 40),
    NULL::bigint,
    CASE WHEN COALESCE(source.row_data->>'created_at', '')
        ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((source.row_data->>'created_at')::double precision)
        ELSE now() END,
    now()
FROM source_rows AS source
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO UPDATE SET
    name = EXCLUDED.name,
    phone = EXCLUDED.phone,
    note = EXCLUDED.note,
    due = EXCLUDED.due,
    updated_at = now()
"""


TRANSACTION_BACKFILL_SQL = _source_ctes(("qarz_transactions", "qarz_tx")) + r""",
transaction_sources AS (
    SELECT DISTINCT ON (
        account_id,
        COALESCE(NULLIF(row_data->>'id', ''), resource || ':' || source_key)
    ) account_id, resource, source_key, ordinal, row_data
    FROM source_rows
    ORDER BY
        account_id,
        COALESCE(NULLIF(row_data->>'id', ''), resource || ':' || source_key),
        CASE resource WHEN 'qarz_transactions' THEN 0 ELSE 1 END,
        ordinal
)
INSERT INTO debt_transactions (
    business_account_id, debtor_id, legacy_source_id, transaction_type,
    amount, transaction_date, note, order_id, cash_receipt_id,
    performed_by_staff_id, created_at
)
SELECT
    source.account_id,
    debtor.id,
    CASE WHEN COALESCE(source.row_data->>'id', source.source_key, '') ~ '^[0-9]+$'
        THEN COALESCE(source.row_data->>'id', source.source_key)::bigint
        ELSE NULL END,
    source.row_data->>'type',
    (source.row_data->>'amount')::bigint,
    CASE WHEN pg_input_is_valid(COALESCE(source.row_data->>'date', ''), 'date')
        THEN (source.row_data->>'date')::date
        WHEN COALESCE(source.row_data->>'created_at', '') ~ '^[0-9]+([.][0-9]+)?$'
        THEN (to_timestamp((source.row_data->>'created_at')::double precision)
              AT TIME ZONE 'Asia/Tashkent')::date
        ELSE (now() AT TIME ZONE 'Asia/Tashkent')::date END,
    left(COALESCE(source.row_data->>'note', ''), 200),
    NULL::bigint,
    NULL::bigint,
    NULL::bigint,
    CASE WHEN COALESCE(source.row_data->>'created_at', '')
        ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((source.row_data->>'created_at')::double precision)
        ELSE now() END
FROM transaction_sources AS source
JOIN debtors AS debtor
  ON debtor.business_account_id = source.account_id
 AND debtor.legacy_source_id = CASE
    WHEN COALESCE(source.row_data->>'debtor_id', '') ~ '^[0-9]+$'
    THEN (source.row_data->>'debtor_id')::bigint ELSE NULL END
WHERE source.row_data->>'type' IN ('debt','payment')
  AND COALESCE(source.row_data->>'amount', '') ~ '^[0-9]+$'
  AND (source.row_data->>'amount')::bigint > 0
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO UPDATE SET
    debtor_id = EXCLUDED.debtor_id,
    transaction_type = EXCLUDED.transaction_type,
    amount = EXCLUDED.amount,
    transaction_date = EXCLUDED.transaction_date,
    note = EXCLUDED.note
"""


CASH_LINK_BACKFILL_SQL = _source_ctes(("sales",)) + r""",
resolved AS (
    SELECT DISTINCT ON (source.account_id, source.source_key)
        source.account_id,
        source.source_key,
        CASE WHEN COALESCE(source.row_data->>'qarz_tx_id', '') ~ '^[0-9]+$'
            THEN (source.row_data->>'qarz_tx_id')::bigint ELSE NULL END
            AS legacy_transaction_id,
        line.receipt_id
    FROM source_rows AS source
    JOIN cash_receipt_lines AS line
      ON line.business_account_id = source.account_id
     AND line.legacy_source_key = 'sales:' || source.source_key
    WHERE COALESCE(source.row_data->>'qarz_tx_id', '') ~ '^[0-9]+$'
    ORDER BY source.account_id, source.source_key, line.id
)
UPDATE debt_transactions AS transaction
SET cash_receipt_id = resolved.receipt_id,
    order_id = COALESCE(transaction.order_id, receipt.order_id)
FROM resolved
JOIN cash_receipts AS receipt ON receipt.id = resolved.receipt_id
WHERE transaction.business_account_id = resolved.account_id
  AND transaction.legacy_source_id = resolved.legacy_transaction_id
"""


RECEIPT_DEBTOR_BACKFILL_SQL = r"""
UPDATE cash_receipts AS receipt
SET debtor_id = debtor.id,
    debtor_name_snapshot = CASE
        WHEN receipt.debtor_name_snapshot = '' THEN debtor.name
        ELSE receipt.debtor_name_snapshot END
FROM debtors AS debtor
WHERE debtor.business_account_id = receipt.business_account_id
  AND debtor.legacy_source_id = receipt.legacy_debtor_source_id
"""


ORDER_DEBTOR_BACKFILL_SQL = r"""
UPDATE orders AS target_order
SET debtor_id = receipt.debtor_id
FROM cash_receipts AS receipt
WHERE receipt.order_id = target_order.id
  AND receipt.pay_type = 'qarz'
  AND receipt.debtor_id IS NOT NULL
"""


def upgrade() -> None:
    op.create_table(
        "debtors",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("due", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("created_by_staff_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name="ck_debtors_name_required"
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_staff_id"], ["staff_members.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_debtors_business_created",
        "debtors",
        ["business_account_id", "created_at", "id"],
    )
    op.create_index(
        "uq_debtors_business_legacy",
        "debtors",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_table(
        "debt_transactions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("debtor_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("transaction_type", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("order_id", sa.BigInteger()),
        sa.Column("cash_receipt_id", sa.BigInteger()),
        sa.Column("performed_by_staff_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "transaction_type IN ('debt','payment')",
            name="ck_debt_transactions_type",
        ),
        sa.CheckConstraint(
            "amount > 0", name="ck_debt_transactions_amount_positive"
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["debtor_id"], ["debtors.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["cash_receipt_id"], ["cash_receipts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["performed_by_staff_id"], ["staff_members.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_debt_transactions_debtor_date",
        "debt_transactions",
        ["business_account_id", "debtor_id", "transaction_date", "id"],
    )
    op.create_index(
        "ix_debt_transactions_receipt",
        "debt_transactions",
        ["business_account_id", "cash_receipt_id"],
    )
    op.create_index(
        "uq_debt_transactions_business_legacy",
        "debt_transactions",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "uq_debt_transactions_order_debt",
        "debt_transactions",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text(
            "order_id IS NOT NULL AND transaction_type = 'debt'"
        ),
    )
    op.add_column("cash_receipts", sa.Column("debtor_id", sa.BigInteger()))
    op.create_foreign_key(
        "fk_cash_receipts_debtor_id",
        "cash_receipts",
        "debtors",
        ["debtor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_cash_receipts_debtor",
        "cash_receipts",
        ["business_account_id", "debtor_id"],
    )
    op.add_column("orders", sa.Column("debtor_id", sa.BigInteger()))
    op.create_foreign_key(
        "fk_orders_debtor_id",
        "orders",
        "debtors",
        ["debtor_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(DEBTOR_BACKFILL_SQL)
    op.execute(TRANSACTION_BACKFILL_SQL)
    op.execute(CASH_LINK_BACKFILL_SQL)
    op.execute(RECEIPT_DEBTOR_BACKFILL_SQL)
    op.execute(ORDER_DEBTOR_BACKFILL_SQL)


def downgrade() -> None:
    op.drop_constraint("fk_orders_debtor_id", "orders", type_="foreignkey")
    op.drop_column("orders", "debtor_id")
    op.drop_index("ix_cash_receipts_debtor", table_name="cash_receipts")
    op.drop_constraint(
        "fk_cash_receipts_debtor_id", "cash_receipts", type_="foreignkey"
    )
    op.drop_column("cash_receipts", "debtor_id")
    op.drop_index(
        "uq_debt_transactions_order_debt", table_name="debt_transactions"
    )
    op.drop_index(
        "uq_debt_transactions_business_legacy", table_name="debt_transactions"
    )
    op.drop_index(
        "ix_debt_transactions_receipt", table_name="debt_transactions"
    )
    op.drop_index(
        "ix_debt_transactions_debtor_date", table_name="debt_transactions"
    )
    op.drop_table("debt_transactions")
    op.drop_index("uq_debtors_business_legacy", table_name="debtors")
    op.drop_index("ix_debtors_business_created", table_name="debtors")
    op.drop_table("debtors")
