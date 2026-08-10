"""Mutaxassislikni typed PostgreSQL domeniga ko'chirish.

Revision ID: 0039_specialists_domain
Revises: 0038_documents_domain

Eski user_profiles.specialist_profile JSONi hamda kabinetdagi
specialist_credentials, specialist_offers va specialist_portfolio resurslari
idempotent tarzda yangi jadvallarga ko'chiriladi. Eski JSON rollback uchun
o'z joyida qoladi, yangi live o'qish/yozish esa typed jadvallardan bajariladi.
"""

from alembic import op
import sqlalchemy as sa


revision = "0039_specialists_domain"
down_revision = "0038_documents_domain"
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


PROFILE_BACKFILL_SQL = r"""
INSERT INTO specialist_profiles (
    user_account_id, profession, description, price_text, service_area,
    is_government, organization, department, position, work_hours,
    after_hours, visible, available, latitude, longitude, created_at, updated_at
)
SELECT
    profile.account_id,
    left(COALESCE(
        NULLIF(trim(profile.specialist_profile::jsonb->>'profession'), ''),
        NULLIF(trim(profile.specialist_profile::jsonb->>'kasb'), ''), ''
    ), 180),
    left(COALESCE(
        NULLIF(trim(profile.specialist_profile::jsonb->>'description'), ''),
        NULLIF(trim(profile.specialist_profile::jsonb->>'descr'), ''), ''
    ), 3000),
    left(COALESCE(
        NULLIF(trim(profile.specialist_profile::jsonb->>'price_text'), ''),
        NULLIF(trim(profile.specialist_profile::jsonb->>'narx'), ''), ''
    ), 120),
    left(COALESCE(profile.specialist_profile::jsonb->>'hudud', ''), 180),
    lower(COALESCE(profile.specialist_profile::jsonb->>'is_gov', 'false'))
        IN ('1', 'true', 'yes', 'on'),
    left(COALESCE(profile.specialist_profile::jsonb->>'org', ''), 180),
    left(COALESCE(profile.specialist_profile::jsonb->>'dept', ''), 180),
    left(COALESCE(profile.specialist_profile::jsonb->>'lavozim', ''), 180),
    left(COALESCE(profile.specialist_profile::jsonb->>'work_hours', ''), 120),
    left(COALESCE(profile.specialist_profile::jsonb->>'after_hours', ''), 120),
    lower(COALESCE(profile.specialist_profile::jsonb->>'visible', 'false'))
        IN ('1', 'true', 'yes', 'on'),
    lower(COALESCE(profile.specialist_profile::jsonb->>'available', 'true'))
        NOT IN ('0', 'false', 'no', 'off'),
    CASE
        WHEN COALESCE(profile.specialist_profile::jsonb->>'lat', '')
             ~ '^-?[0-9]+([.][0-9]+)?$'
         AND (profile.specialist_profile::jsonb->>'lat')::double precision
             BETWEEN -90 AND 90
        THEN (profile.specialist_profile::jsonb->>'lat')::double precision
        ELSE profile.latitude
    END,
    CASE
        WHEN COALESCE(profile.specialist_profile::jsonb->>'lng', '')
             ~ '^-?[0-9]+([.][0-9]+)?$'
         AND (profile.specialist_profile::jsonb->>'lng')::double precision
             BETWEEN -180 AND 180
        THEN (profile.specialist_profile::jsonb->>'lng')::double precision
        ELSE profile.longitude
    END,
    CASE
        WHEN COALESCE(profile.specialist_profile::jsonb->>'created_at', '')
             ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp(
            (profile.specialist_profile::jsonb->>'created_at')::double precision
        )
        ELSE now()
    END,
    now()
FROM user_profiles AS profile
WHERE jsonb_typeof(COALESCE(profile.specialist_profile::jsonb, '{}'::jsonb))
      = 'object'
  AND COALESCE(profile.specialist_profile::jsonb, '{}'::jsonb) <> '{}'::jsonb
ON CONFLICT (user_account_id) DO NOTHING
"""


def _resource_source(resource: str) -> str:
    return rf"""
WITH relational_rows AS (
    SELECT
        resource.account_id,
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
    WHERE resource.account_type = 'user'
      AND resource.resource = '{resource}'
    GROUP BY resource.account_id, record.id, record.source_key, record.ordinal
),
payload_rows AS (
    SELECT
        profile.account_id,
        COALESCE(
            NULLIF(entry.row_data->>'id', ''),
            'ordinal:{resource}:' || entry.ordinality
        ) AS source_key,
        entry.ordinality::integer AS ordinal,
        entry.row_data,
        1 AS storage_priority
    FROM user_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(
                COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
                -> '{resource}'
            ) = 'array'
            THEN COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
                -> '{resource}'
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
),
ranked_rows AS (
    SELECT *,
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
        account_id, row_data,
        CASE
            WHEN COALESCE(NULLIF(row_data->>'id', ''), source_key, '') ~ '^[0-9]+$'
            THEN COALESCE(NULLIF(row_data->>'id', ''), source_key)::bigint
            ELSE NULL
        END AS legacy_source_id,
        ordinal
    FROM ranked_rows
    ORDER BY account_id, dedupe_key, storage_priority, ordinal
)
"""


CREDENTIAL_BACKFILL_SQL = _resource_source("specialist_credentials") + r"""
INSERT INTO specialist_credentials (
    user_account_id, legacy_source_id, object_key, legacy_media_url,
    position, created_at
)
SELECT
    account_id,
    legacy_source_id,
    '',
    left(COALESCE(row_data->>'file_url', ''), 2048),
    CASE
        WHEN COALESCE(row_data->>'pos', '') ~ '^-?[0-9]+$'
        THEN (row_data->>'pos')::integer ELSE ordinal
    END,
    CASE
        WHEN COALESCE(row_data->>'created_at', '') ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((row_data->>'created_at')::double precision)
        ELSE now()
    END
FROM source_rows
WHERE COALESCE(row_data->>'file_url', '') <> ''
ON CONFLICT (user_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO NOTHING
"""


OFFER_BACKFILL_SQL = _resource_source("specialist_offers") + r"""
INSERT INTO specialist_offers (
    user_account_id, legacy_source_id, kind, name, price_text, note,
    image_object_key, legacy_image_url, created_at, updated_at
)
SELECT
    account_id,
    legacy_source_id,
    CASE WHEN row_data->>'kind' = 'product' THEN 'product' ELSE 'service' END,
    left(COALESCE(NULLIF(trim(row_data->>'name'), ''), 'Nomsiz taklif'), 160),
    left(COALESCE(row_data->>'price', row_data->>'price_text', ''), 120),
    left(COALESCE(row_data->>'note', ''), 1000),
    '',
    left(COALESCE(row_data->>'photo_file', row_data->>'image_url', ''), 2048),
    CASE
        WHEN COALESCE(row_data->>'created_at', '') ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((row_data->>'created_at')::double precision)
        ELSE now()
    END,
    now()
FROM source_rows
ON CONFLICT (user_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO NOTHING
"""


PORTFOLIO_BACKFILL_SQL = _resource_source("specialist_portfolio") + r"""
INSERT INTO specialist_portfolio (
    user_account_id, legacy_source_id, media_type, object_key,
    legacy_media_url, created_at
)
SELECT
    account_id,
    legacy_source_id,
    CASE WHEN row_data->>'media_type' = 'video' THEN 'video' ELSE 'photo' END,
    '',
    left(COALESCE(row_data->>'file_url', ''), 2048),
    CASE
        WHEN COALESCE(row_data->>'created_at', '') ~ '^[0-9]+([.][0-9]+)?$'
        THEN to_timestamp((row_data->>'created_at')::double precision)
        ELSE now()
    END
FROM source_rows
WHERE COALESCE(row_data->>'file_url', '') <> ''
ON CONFLICT (user_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO NOTHING
"""


def upgrade() -> None:
    op.create_table(
        "specialist_profiles",
        sa.Column(
            "user_account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("profession", sa.String(180), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("price_text", sa.String(120), nullable=False, server_default=""),
        sa.Column("service_area", sa.String(180), nullable=False, server_default=""),
        sa.Column("is_government", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("organization", sa.String(180), nullable=False, server_default=""),
        sa.Column("department", sa.String(180), nullable=False, server_default=""),
        sa.Column("position", sa.String(180), nullable=False, server_default=""),
        sa.Column("work_hours", sa.String(120), nullable=False, server_default=""),
        sa.Column("after_hours", sa.String(120), nullable=False, server_default=""),
        sa.Column("visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name="ck_specialist_profiles_latitude",
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name="ck_specialist_profiles_longitude",
        ),
    )
    op.create_index(
        "ix_specialist_profiles_visible_location",
        "specialist_profiles",
        ["visible", "latitude", "longitude"],
    )
    op.create_table(
        "specialist_credentials",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "user_account_id", sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("object_key", sa.String(600), nullable=False, server_default=""),
        sa.Column("legacy_media_url", sa.String(2048), nullable=False, server_default=""),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_specialist_credentials_user_position",
        "specialist_credentials",
        ["user_account_id", "position", "id"],
    )
    op.create_index(
        "uq_specialist_credentials_user_legacy",
        "specialist_credentials",
        ["user_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_table(
        "specialist_offers",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "user_account_id", sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("kind", sa.String(12), nullable=False, server_default="service"),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("price_text", sa.String(120), nullable=False, server_default=""),
        sa.Column("note", sa.String(1000), nullable=False, server_default=""),
        sa.Column("image_object_key", sa.String(600), nullable=False, server_default=""),
        sa.Column("legacy_image_url", sa.String(2048), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('service', 'product')", name="ck_specialist_offers_kind"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_specialist_offers_name_required"),
    )
    op.create_index(
        "ix_specialist_offers_user_created",
        "specialist_offers",
        ["user_account_id", "created_at", "id"],
    )
    op.create_index(
        "uq_specialist_offers_user_legacy",
        "specialist_offers",
        ["user_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_table(
        "specialist_portfolio",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "user_account_id", sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("media_type", sa.String(12), nullable=False, server_default="photo"),
        sa.Column("object_key", sa.String(600), nullable=False, server_default=""),
        sa.Column("legacy_media_url", sa.String(2048), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "media_type IN ('photo', 'video')",
            name="ck_specialist_portfolio_media_type",
        ),
    )
    op.create_index(
        "ix_specialist_portfolio_user_created",
        "specialist_portfolio",
        ["user_account_id", "created_at", "id"],
    )
    op.create_index(
        "uq_specialist_portfolio_user_legacy",
        "specialist_portfolio",
        ["user_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )

    op.execute(PROFILE_BACKFILL_SQL)
    op.execute(CREDENTIAL_BACKFILL_SQL)
    op.execute(OFFER_BACKFILL_SQL)
    op.execute(PORTFOLIO_BACKFILL_SQL)


def downgrade() -> None:
    op.drop_index("uq_specialist_portfolio_user_legacy", table_name="specialist_portfolio")
    op.drop_index("ix_specialist_portfolio_user_created", table_name="specialist_portfolio")
    op.drop_table("specialist_portfolio")
    op.drop_index("uq_specialist_offers_user_legacy", table_name="specialist_offers")
    op.drop_index("ix_specialist_offers_user_created", table_name="specialist_offers")
    op.drop_table("specialist_offers")
    op.drop_index("uq_specialist_credentials_user_legacy", table_name="specialist_credentials")
    op.drop_index("ix_specialist_credentials_user_position", table_name="specialist_credentials")
    op.drop_table("specialist_credentials")
    op.drop_index("ix_specialist_profiles_visible_location", table_name="specialist_profiles")
    op.drop_table("specialist_profiles")
