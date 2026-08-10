"""Hujjatlar va kontragentlarni typed PostgreSQL domeniga ko'chirish.

Revision ID: 0038_documents_domain
Revises: 0037_inventory_live_completion

Kabinetning eski `documents`/`contractors` resurslari o'qiladi. Mavjud profil
JSONi fallback bo'lib qoladi, ammo yangi yozuvlar endi alohida jadvallarda
saqlanadi. Backfill faqat yetishmayotgan legacy identifikatorlarni qo'shadi.
"""

from alembic import op
import sqlalchemy as sa


revision = "0038_documents_domain"
down_revision = "0037_inventory_live_completion"
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


def _source_ctes(resources: tuple[str, ...], priorities: dict[str, int]) -> str:
    names = ", ".join(f"'{name}'" for name in resources)
    values = ", ".join(f"('{name}')" for name in resources)
    cases = " ".join(
        f"WHEN '{name}' THEN {priority}"
        for name, priority in priorities.items()
    )
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
        0 AS storage_priority
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
        COALESCE(
            NULLIF(entry.row_data->>'id', ''),
            'ordinal:' || resource_name.resource || ':' || entry.ordinality
        ) AS source_key,
        entry.ordinality::integer AS ordinal,
        entry.row_data,
        1 AS storage_priority
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
),
ranked_rows AS (
    SELECT *,
        CASE resource {cases} ELSE 99 END AS resource_priority,
        CASE
            WHEN COALESCE(NULLIF(row_data->>'id', ''), source_key, '') ~ '^[0-9]+$'
            THEN 'id:' || COALESCE(NULLIF(row_data->>'id', ''), source_key)
            ELSE 'row:' || md5(row_data::text)
        END AS dedupe_key
    FROM (
        SELECT * FROM relational_rows
        UNION ALL
        SELECT * FROM payload_rows
    ) AS combined
),
source_rows AS (
    SELECT DISTINCT ON (account_id, dedupe_key)
        account_id, resource, source_key, row_data,
        CASE
            WHEN COALESCE(NULLIF(row_data->>'id', ''), source_key, '') ~ '^[0-9]+$'
            THEN COALESCE(NULLIF(row_data->>'id', ''), source_key)::bigint
            ELSE NULL
        END AS legacy_source_id
    FROM ranked_rows
    ORDER BY account_id, dedupe_key, storage_priority, resource_priority, ordinal
)
"""


COUNTERPARTY_SOURCE = _source_ctes(
    ("contractors", "counterparties"),
    {"contractors": 0, "counterparties": 1},
)


DOCUMENT_SOURCE = _source_ctes(
    (
        "documents",
        "business_documents",
        "incoming_documents",
        "outgoing_documents",
        "internal_documents",
    ),
    {
        "documents": 0,
        "business_documents": 1,
        "incoming_documents": 2,
        "outgoing_documents": 3,
        "internal_documents": 4,
    },
)


COUNTERPARTY_BACKFILL_SQL = "WITH\n" + COUNTERPARTY_SOURCE + r"""
INSERT INTO document_counterparties (
    business_account_id, legacy_source_id, name, ctype, director, phone,
    address, inn, account, bank, mfo, note, created_at, updated_at
)
SELECT
    source.account_id,
    source.legacy_source_id,
    left(COALESCE(NULLIF(trim(source.row_data->>'name'), ''),
         'Nomsiz kontragent'), 200),
    left(COALESCE(source.row_data->>'ctype', ''), 40),
    left(COALESCE(source.row_data->>'director', ''), 120),
    left(COALESCE(source.row_data->>'phone', ''), 40),
    left(COALESCE(source.row_data->>'address', ''), 200),
    left(COALESCE(source.row_data->>'inn', ''), 20),
    left(COALESCE(source.row_data->>'account', ''), 40),
    left(COALESCE(source.row_data->>'bank', ''), 120),
    left(COALESCE(source.row_data->>'mfo', ''), 20),
    left(COALESCE(source.row_data->>'note', ''), 300),
    CASE
        WHEN COALESCE(source.row_data->>'created_at', '') ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((source.row_data->>'created_at')::double precision)
        ELSE now()
    END,
    now()
FROM source_rows AS source
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO NOTHING
"""


DOCUMENT_BACKFILL_SQL = "WITH\n" + DOCUMENT_SOURCE + r"""
INSERT INTO business_documents (
    business_account_id, legacy_source_id, direction, doc_type, title, number,
    doc_date, contractor_id, body, sender_business_id, sender_name_snapshot,
    receiver_tax_id, status, source_document_id, responded_at, created_at,
    updated_at
)
SELECT
    source.account_id,
    source.legacy_source_id,
    CASE
        WHEN source.row_data->>'direction' IN ('ichki', 'kiruvchi', 'chiquvchi')
        THEN source.row_data->>'direction'
        WHEN source.resource = 'incoming_documents' THEN 'kiruvchi'
        WHEN source.resource = 'outgoing_documents' THEN 'chiquvchi'
        ELSE 'ichki'
    END,
    left(COALESCE(source.row_data->>'doc_type', ''), 60),
    left(COALESCE(source.row_data->>'title', ''), 200),
    left(COALESCE(source.row_data->>'number', ''), 40),
    left(COALESCE(source.row_data->>'doc_date', ''), 20),
    contractor.id,
    COALESCE(source.row_data->>'body', ''),
    COALESCE(sender_map.target_id, sender_direct.id),
    left(COALESCE(
        NULLIF(source.row_data->>'sender_name', ''),
        sender_profile.name,
        ''
    ), 120),
    left(COALESCE(source.row_data->>'receiver_inn', ''), 20),
    CASE
        WHEN source.row_data->>'status' IN (
            '', 'yuborilgan', 'kutilmoqda', 'qabul qilindi', 'rad etildi'
        ) THEN source.row_data->>'status'
        ELSE ''
    END,
    NULL,
    CASE
        WHEN source.row_data->>'status' IN ('qabul qilindi', 'rad etildi')
        THEN now() ELSE NULL
    END,
    CASE
        WHEN COALESCE(source.row_data->>'created_at', '') ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((source.row_data->>'created_at')::double precision)
        ELSE now()
    END,
    now()
FROM source_rows AS source
LEFT JOIN document_counterparties AS contractor
  ON contractor.business_account_id = source.account_id
 AND contractor.legacy_source_id = CASE
        WHEN COALESCE(source.row_data->>'contractor_id', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'contractor_id')::bigint ELSE NULL END
LEFT JOIN legacy_id_map AS sender_map
  ON sender_map.entity_type = 'business_account'
 AND sender_map.legacy_id = CASE
        WHEN COALESCE(source.row_data->>'sender_business_id', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'sender_business_id')::bigint ELSE NULL END
 AND sender_map.target_id IS NOT NULL
LEFT JOIN accounts AS sender_direct
  ON sender_direct.id = CASE
        WHEN COALESCE(source.row_data->>'sender_business_id', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'sender_business_id')::bigint ELSE NULL END
 AND sender_direct.account_type = 'business'
LEFT JOIN business_profiles AS sender_profile
  ON sender_profile.account_id = COALESCE(sender_map.target_id, sender_direct.id)
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO NOTHING
"""


LINK_INCOMING_SQL = r"""
UPDATE business_documents AS incoming
SET source_document_id = (
    SELECT outgoing.id
    FROM business_documents AS outgoing
    WHERE outgoing.business_account_id = incoming.sender_business_id
      AND outgoing.direction = 'chiquvchi'
      AND outgoing.doc_type = incoming.doc_type
      AND outgoing.number = incoming.number
      AND outgoing.body = incoming.body
    ORDER BY outgoing.id DESC
    LIMIT 1
)
WHERE incoming.direction = 'kiruvchi'
  AND incoming.sender_business_id IS NOT NULL
  AND incoming.source_document_id IS NULL
  AND EXISTS (
      SELECT 1
      FROM business_documents AS outgoing
      WHERE outgoing.business_account_id = incoming.sender_business_id
        AND outgoing.direction = 'chiquvchi'
        AND outgoing.doc_type = incoming.doc_type
        AND outgoing.number = incoming.number
        AND outgoing.body = incoming.body
  )
"""


def upgrade() -> None:
    op.create_table(
        "document_counterparties",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "business_account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("ctype", sa.String(40), nullable=False, server_default=""),
        sa.Column("director", sa.String(120), nullable=False, server_default=""),
        sa.Column("phone", sa.String(40), nullable=False, server_default=""),
        sa.Column("address", sa.String(200), nullable=False, server_default=""),
        sa.Column("inn", sa.String(20), nullable=False, server_default=""),
        sa.Column("account", sa.String(40), nullable=False, server_default=""),
        sa.Column("bank", sa.String(120), nullable=False, server_default=""),
        sa.Column("mfo", sa.String(20), nullable=False, server_default=""),
        sa.Column("note", sa.String(300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_document_counterparties_name_required",
        ),
    )
    op.create_index(
        "ix_document_counterparties_business_name",
        "document_counterparties",
        ["business_account_id", "name", "id"],
    )
    op.create_index(
        "uq_document_counterparties_business_legacy",
        "document_counterparties",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )

    op.create_table(
        "business_documents",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "business_account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("doc_type", sa.String(60), nullable=False, server_default=""),
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
        sa.Column("number", sa.String(40), nullable=False, server_default=""),
        sa.Column("doc_date", sa.String(20), nullable=False, server_default=""),
        sa.Column(
            "contractor_id",
            sa.BigInteger(),
            sa.ForeignKey("document_counterparties.id", ondelete="SET NULL"),
        ),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "sender_business_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "sender_name_snapshot", sa.String(120), nullable=False, server_default=""
        ),
        sa.Column(
            "receiver_tax_id", sa.String(20), nullable=False, server_default=""
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default=""),
        sa.Column(
            "source_document_id",
            sa.BigInteger(),
            sa.ForeignKey("business_documents.id", ondelete="SET NULL"),
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "direction IN ('ichki', 'kiruvchi', 'chiquvchi')",
            name="ck_business_documents_direction",
        ),
        sa.CheckConstraint(
            "status IN ('', 'yuborilgan', 'kutilmoqda', "
            "'qabul qilindi', 'rad etildi')",
            name="ck_business_documents_status",
        ),
    )
    op.create_index(
        "ix_business_documents_business_direction",
        "business_documents",
        ["business_account_id", "direction", sa.text("id DESC")],
    )
    op.create_index(
        "uq_business_documents_business_legacy",
        "business_documents",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "ix_business_documents_source",
        "business_documents",
        ["source_document_id"],
    )
    op.execute(sa.text(
        "CREATE INDEX ix_business_profiles_tax_id_documents "
        "ON business_profiles ((replace(replace(replace(replace(replace("
        "replace(tax_id, ' ', ''), '-', ''), '.', ''), '/', ''), '(', ''), ')', ''))) "
        "WHERE tax_id <> ''"
    ))

    op.execute(sa.text(COUNTERPARTY_BACKFILL_SQL))
    op.execute(sa.text(DOCUMENT_BACKFILL_SQL))
    op.execute(sa.text(LINK_INCOMING_SQL))


def downgrade() -> None:
    op.drop_index("ix_business_profiles_tax_id_documents", table_name="business_profiles")
    op.drop_table("business_documents")
    op.drop_table("document_counterparties")
