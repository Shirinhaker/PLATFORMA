"""Obunalar uchun relatsion jadval.

Obunalar hozirgacha kabinet JSON'ida saqlanardi va faqat o'qib
ko'rsatilardi — obuna bo'lish oqimi umuman yo'q edi. Jadval qo'shilgach
obuna bo'lish/bekor qilish ishlaydi va obunachilar soni jadvaldan
hisoblanadi.

Eski yozuvlarda nishon `target_id` eski identifikator bilan yozilgan;
backfill uni `legacy_id_map` orqali akkaunt identifikatoriga
xaritalaydi. Xaritasi topilmagan yozuv tashlab yuboriladi — u yo'q
profilga ishora qiladi.
"""

from alembic import op
import sqlalchemy as sa


revision = "0023_profile_follows"
down_revision = "0022_education_group_history"
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


def _backfill_sql(account_type: str, resource: str, profile_table: str) -> str:
    return rf"""
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
    WHERE resource.account_type = '{account_type}'
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
    FROM {profile_table} AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(
            COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb) -> '{resource}'
        ) = 'array'
        THEN COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb) -> '{resource}'
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
INSERT INTO profile_follows (
    follower_account_id, target_account_id, target_kind, created_at
)
SELECT DISTINCT
    source.account_id,
    mapping.target_id,
    CASE WHEN source.row_data->>'target_kind' = 'business'
        THEN 'business' ELSE 'user' END,
    CASE WHEN COALESCE(source.row_data->>'created_at', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'created_at')::bigint
        ELSE EXTRACT(EPOCH FROM now())::bigint END
FROM source_rows AS source
JOIN legacy_id_map AS mapping
    ON mapping.entity_type = (
        CASE WHEN source.row_data->>'target_kind' = 'business'
            THEN 'business_account' ELSE 'user_account' END
    )
   AND mapping.legacy_id = (
        CASE WHEN COALESCE(source.row_data->>'target_id', '') ~ '^[0-9]+$'
            THEN (source.row_data->>'target_id')::bigint ELSE NULL END
    )
   AND mapping.target_id IS NOT NULL
WHERE mapping.target_id <> source.account_id
ON CONFLICT (follower_account_id, target_account_id) DO NOTHING
"""


RECOUNT_SQL = """
UPDATE user_profiles AS profile SET
    followers_count = COALESCE(counts.followers, 0),
    following_count = COALESCE(counts.following, 0)
FROM (
    SELECT
        account.id AS account_id,
        (SELECT COUNT(*) FROM profile_follows f
            WHERE f.target_account_id = account.id) AS followers,
        (SELECT COUNT(*) FROM profile_follows f
            WHERE f.follower_account_id = account.id) AS following
    FROM accounts AS account
) AS counts
WHERE counts.account_id = profile.account_id;

UPDATE business_profiles AS profile SET
    followers_count = COALESCE(counts.followers, 0),
    following_count = COALESCE(counts.following, 0)
FROM (
    SELECT
        account.id AS account_id,
        (SELECT COUNT(*) FROM profile_follows f
            WHERE f.target_account_id = account.id) AS followers,
        (SELECT COUNT(*) FROM profile_follows f
            WHERE f.follower_account_id = account.id) AS following
    FROM accounts AS account
) AS counts
WHERE counts.account_id = profile.account_id;
"""


def upgrade() -> None:
    op.create_table(
        "profile_follows",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("follower_account_id", sa.BigInteger(), nullable=False),
        sa.Column("target_account_id", sa.BigInteger(), nullable=False),
        sa.Column("target_kind", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "target_kind IN ('user', 'business')",
            name="ck_profile_follows_target_kind",
        ),
        sa.CheckConstraint(
            "follower_account_id <> target_account_id",
            name="ck_profile_follows_not_self",
        ),
        sa.ForeignKeyConstraint(
            ["follower_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "uq_profile_follows_pair",
        "profile_follows",
        ["follower_account_id", "target_account_id"],
        unique=True,
    )
    op.create_index(
        "ix_profile_follows_target",
        "profile_follows",
        ["target_account_id", "id"],
    )
    op.create_index(
        "ix_profile_follows_follower",
        "profile_follows",
        ["follower_account_id", "created_at", "id"],
    )

    op.execute(_backfill_sql("user", "follows", "user_profiles"))
    op.execute(_backfill_sql("business", "following", "business_profiles"))
    op.execute(RECOUNT_SQL)


def downgrade() -> None:
    op.drop_table("profile_follows")
