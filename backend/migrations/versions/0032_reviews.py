"""v1656 baholar va mijoz fikrlari domeni.

Revision ID: 0032_reviews
Revises: 0031_messages
"""

from alembic import op
import sqlalchemy as sa


revision = "0032_reviews"
down_revision = "0031_messages"
branch_labels = None
depends_on = None


# Bir review user va business kabinet JSONlarida takrorlangan. Relatsion kabinet
# yozuvi ustuvor, DISTINCT ON esa bir xil legacy_source_id ni bitta qiladi.
REVIEW_SOURCE_CTES = r"""
relational_review_rows AS (
    SELECT
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
    WHERE resource.resource IN (
        'business_reviews', 'reviews', 'reviews_received', 'reviews_given'
    )
    GROUP BY record.id, record.source_key
),
business_payload_review_rows AS (
    SELECT
        COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality),
        entry.row_data,
        1 AS priority
    FROM business_profiles AS profile
    CROSS JOIN LATERAL (VALUES ('business_reviews'), ('reviews')) AS resource(name)
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(
            COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)
                -> resource.name
        ) = 'array'
        THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)
                -> resource.name
        ELSE '[]'::jsonb END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
),
user_payload_review_rows AS (
    SELECT
        COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality),
        entry.row_data,
        1 AS priority
    FROM user_profiles AS profile
    CROSS JOIN LATERAL (VALUES ('reviews_received'), ('reviews_given'))
        AS resource(name)
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(
            COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)
                -> resource.name
        ) = 'array'
        THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)
                -> resource.name
        ELSE '[]'::jsonb END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
),
all_review_rows AS (
    SELECT * FROM relational_review_rows
    UNION ALL SELECT * FROM business_payload_review_rows
    UNION ALL SELECT * FROM user_payload_review_rows
),
review_source AS (
    SELECT DISTINCT ON (eligible.legacy_source_id)
        eligible.legacy_source_id,
        eligible.row_data
    FROM (
        SELECT
            CASE
                WHEN COALESCE(NULLIF(row_data->>'id', ''), source_key, '')
                     ~ '^[0-9]+$'
                THEN COALESCE(NULLIF(row_data->>'id', ''), source_key)::bigint
                ELSE NULL
            END AS legacy_source_id,
            row_data,
            priority
        FROM all_review_rows
    ) AS eligible
    WHERE eligible.legacy_source_id IS NOT NULL
      AND COALESCE(eligible.row_data->>'target_kind', '')
            IN ('business', 'user', 'specialist')
      AND COALESCE(eligible.row_data->>'target_id', '') ~ '^[0-9]+$'
      AND COALESCE(eligible.row_data->>'reviewer_user_id', '') ~ '^[0-9]+$'
      AND COALESCE(eligible.row_data->>'stars', '') ~ '^[1-5]$'
    ORDER BY eligible.legacy_source_id, eligible.priority
),
resolved_review_source AS (
    SELECT
        source.legacy_source_id,
        source.row_data,
        CASE WHEN source.row_data->>'target_kind' = 'business'
             THEN 'business' ELSE 'specialist' END AS target_kind,
        target_map.target_id::bigint AS target_account_id,
        reviewer_map.target_id::bigint AS reviewer_account_id,
        target_order.id AS order_id
    FROM review_source AS source
    JOIN legacy_id_map AS target_map
      ON target_map.entity_type = CASE
            WHEN source.row_data->>'target_kind' = 'business'
            THEN 'business_account' ELSE 'user_account' END
     AND target_map.legacy_id = (source.row_data->>'target_id')::bigint
     AND target_map.target_id IS NOT NULL
    JOIN legacy_id_map AS reviewer_map
      ON reviewer_map.entity_type = 'user_account'
     AND reviewer_map.legacy_id =
            (source.row_data->>'reviewer_user_id')::bigint
     AND reviewer_map.target_id IS NOT NULL
    LEFT JOIN orders AS target_order
      ON target_order.legacy_source_id = CASE
            WHEN COALESCE(source.row_data->>'order_id', '') ~ '^[0-9]+$'
            THEN (source.row_data->>'order_id')::bigint ELSE NULL END
    WHERE target_map.target_id <> reviewer_map.target_id
)
"""


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column(
            "specialist_rating_sum",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "user_profiles",
        sa.Column(
            "specialist_rating_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("target_kind", sa.String(length=16), nullable=False),
        sa.Column("target_account_id", sa.BigInteger(), nullable=False),
        sa.Column("reviewer_account_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger()),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner_reply", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner_replied_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "target_kind IN ('business', 'specialist')",
            name="ck_reviews_target_kind",
        ),
        sa.CheckConstraint("stars BETWEEN 1 AND 5", name="ck_reviews_stars"),
        sa.CheckConstraint(
            "reviewer_account_id <> target_account_id",
            name="ck_reviews_not_self",
        ),
        sa.ForeignKeyConstraint(
            ["target_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "uq_reviews_target_reviewer",
        "reviews",
        ["target_kind", "target_account_id", "reviewer_account_id"],
        unique=True,
    )
    op.create_index(
        "ix_reviews_target_created",
        "reviews",
        ["target_kind", "target_account_id", "created_at", "id"],
    )
    op.create_index(
        "ix_reviews_reviewer", "reviews", ["reviewer_account_id", "id"]
    )
    op.create_index("ix_reviews_order", "reviews", ["order_id"])
    op.create_index(
        "uq_reviews_legacy_source",
        "reviews",
        ["legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )

    op.execute(sa.text(f"""
        WITH {REVIEW_SOURCE_CTES}
        INSERT INTO reviews (
            legacy_source_id, target_kind, target_account_id,
            reviewer_account_id, order_id, stars, comment, owner_reply,
            owner_replied_at, created_at, updated_at
        )
        SELECT
            source.legacy_source_id,
            source.target_kind,
            source.target_account_id,
            source.reviewer_account_id,
            source.order_id,
            (source.row_data->>'stars')::integer,
            left(COALESCE(source.row_data->>'comment', ''), 1000),
            left(COALESCE(source.row_data->>'owner_reply', ''), 1500),
            CASE WHEN COALESCE(source.row_data->>'owner_replied_at', '')
                           ~ '^[0-9]+$'
                      AND (source.row_data->>'owner_replied_at')::bigint > 0
                 THEN to_timestamp(
                     (source.row_data->>'owner_replied_at')::double precision
                 ) ELSE NULL END,
            CASE WHEN COALESCE(source.row_data->>'created_at', '') ~ '^[0-9]+$'
                 THEN to_timestamp(
                     (source.row_data->>'created_at')::double precision
                 ) ELSE now() END,
            CASE WHEN COALESCE(source.row_data->>'updated_at', '') ~ '^[0-9]+$'
                 THEN to_timestamp(
                     (source.row_data->>'updated_at')::double precision
                 ) ELSE now() END
        FROM resolved_review_source AS source
        ON CONFLICT DO NOTHING
    """))

    op.execute(sa.text(r"""
        UPDATE business_profiles AS profile
        SET rating_sum = totals.rating_sum,
            rating_count = totals.rating_count
        FROM (
            SELECT account.id AS account_id,
                   COALESCE(SUM(review.stars), 0)::integer AS rating_sum,
                   COUNT(review.id)::integer AS rating_count
            FROM accounts AS account
            LEFT JOIN reviews AS review
              ON review.target_account_id = account.id
             AND review.target_kind = 'business'
            GROUP BY account.id
        ) AS totals
        WHERE totals.account_id = profile.account_id
    """))
    op.execute(sa.text(r"""
        UPDATE user_profiles AS profile
        SET specialist_rating_sum = totals.rating_sum,
            specialist_rating_count = totals.rating_count
        FROM (
            SELECT account.id AS account_id,
                   COALESCE(SUM(review.stars), 0)::integer AS rating_sum,
                   COUNT(review.id)::integer AS rating_count
            FROM accounts AS account
            LEFT JOIN reviews AS review
              ON review.target_account_id = account.id
             AND review.target_kind = 'specialist'
            GROUP BY account.id
        ) AS totals
        WHERE totals.account_id = profile.account_id
    """))


def downgrade() -> None:
    op.drop_index("uq_reviews_legacy_source", table_name="reviews")
    op.drop_index("ix_reviews_order", table_name="reviews")
    op.drop_index("ix_reviews_reviewer", table_name="reviews")
    op.drop_index("ix_reviews_target_created", table_name="reviews")
    op.drop_index("uq_reviews_target_reviewer", table_name="reviews")
    op.drop_table("reviews")
    op.drop_column("user_profiles", "specialist_rating_count")
    op.drop_column("user_profiles", "specialist_rating_sum")
