"""E'lonlarni v1656 oqimi bilan jonli ishlaydigan holatga o'tkazish.

Revision ID: 0008_listings_live_v1656
Revises: 0007_catalog_live_sync
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_listings_live_v1656"
down_revision = "0007_catalog_live_sync"
branch_labels = None
depends_on = None


SOURCE_CTES = r"""
record_rows AS (
    SELECT
        resource.account_id,
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
        ) AS row_data
    FROM cabinet_resources AS resource
    JOIN cabinet_records AS record ON record.resource_id = resource.id
    LEFT JOIN cabinet_record_fields AS field ON field.record_id = record.id
    WHERE resource.account_type = 'business'
      AND resource.resource = 'listings'
    GROUP BY resource.account_id, record.id, record.source_key
),
relational_listings AS (
    SELECT rows.account_id, rows.source_key AS source_record_key, rows.row_data
    FROM record_rows AS rows
),
fallback_listings AS (
    SELECT
        profile.account_id,
        COALESCE(
            NULLIF(entry.row_data->>'id', ''),
            'ordinal:' || (entry.ordinality - 1)
        ) AS source_record_key,
        entry.row_data
    FROM business_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(
                COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'listings'
            ) = 'array'
            THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'listings'
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
    WHERE NOT EXISTS (
        SELECT 1 FROM cabinet_resources AS resource
        WHERE resource.account_id = profile.account_id
          AND resource.account_type = 'business'
          AND resource.resource = 'listings'
    )
),
listing_source AS (
    SELECT * FROM relational_listings
    UNION ALL
    SELECT * FROM fallback_listings
)
"""


SAVED_SOURCE_CTES = r"""
saved_record_rows AS (
    SELECT
        resource.account_id,
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
        ) AS row_data
    FROM cabinet_resources AS resource
    JOIN cabinet_records AS record ON record.resource_id = resource.id
    LEFT JOIN cabinet_record_fields AS field ON field.record_id = record.id
    WHERE resource.account_type = 'user'
      AND resource.resource = 'saved'
    GROUP BY resource.account_id, record.id, record.source_key
),
relational_saved AS (
    SELECT rows.account_id, rows.source_key AS source_record_key, rows.row_data
    FROM saved_record_rows AS rows
),
fallback_saved AS (
    SELECT
        profile.account_id,
        COALESCE(
            NULLIF(entry.row_data->>'id', ''),
            'ordinal:' || (entry.ordinality - 1)
        ) AS source_record_key,
        entry.row_data
    FROM user_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(
                COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'saved'
            ) = 'array'
            THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'saved'
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
    WHERE NOT EXISTS (
        SELECT 1 FROM cabinet_resources AS resource
        WHERE resource.account_id = profile.account_id
          AND resource.account_type = 'user'
          AND resource.resource = 'saved'
    )
),
saved_source AS (
    SELECT * FROM relational_saved
    UNION ALL
    SELECT * FROM fallback_saved
)
"""


def upgrade() -> None:
    op.add_column(
        "listings",
        sa.Column("source_record_key", sa.String(length=160)),
    )
    op.alter_column("listings", "migration_run_id", nullable=True)
    op.alter_column("listing_media", "migration_run_id", nullable=True)
    op.create_index(
        "uq_listings_business_source",
        "listings",
        ["owner_business_account_id", "source_record_key"],
        unique=True,
    )
    op.create_index(
        "ix_listings_public_v1656",
        "listings",
        ["category", "status", "visibility", "review_state", "created_at"],
    )
    op.create_table(
        "listing_saves",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("owner_user_account_id", sa.BigInteger(), nullable=False),
        sa.Column("listing_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_account_id"],
            ["accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listings.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "owner_user_account_id",
            "listing_id",
            name="uq_listing_saves_owner_listing",
        ),
    )
    op.create_index(
        "ix_listing_saves_owner_created",
        "listing_saves",
        ["owner_user_account_id", "created_at"],
    )

    # Phase 3C import qilingan e'lonni o'sha V7 kabinet yozuvi bilan bog'laymiz.
    op.execute(sa.text(f"""
        WITH {SOURCE_CTES}, mapped_listing_source AS (
            SELECT source.account_id, source.source_record_key, mapping.target_id
            FROM listing_source AS source
            JOIN legacy_id_map AS mapping
              ON mapping.entity_type = 'listing'
             AND mapping.legacy_id = CASE
                 WHEN source.source_record_key ~ '^[0-9]+$'
                 THEN source.source_record_key::bigint
                 ELSE NULL
             END
        )
        UPDATE listings AS target
        SET source_record_key = left(mapped.source_record_key, 160)
        FROM mapped_listing_source AS mapped
        WHERE mapped.target_id = target.id
          AND mapped.account_id = target.owner_business_account_id
          AND target.source_record_key IS NULL
    """))

    # V7 jadvali yoki eski cabinet_payload'dagi qolgan biznes e'lonlarini ko'chiramiz.
    op.execute(sa.text(f"""
        WITH {SOURCE_CTES}
        INSERT INTO listings (
            owner_user_account_id, owner_business_account_id,
            source_record_key, category, title, price_text, description,
            address, latitude, longitude, visibility, status, review_state,
            migration_run_id, created_at, updated_at
        )
        SELECT
            NULL,
            source.account_id,
            left(source.source_record_key, 160),
            left(trim(COALESCE(source.row_data->>'cat', source.row_data->>'category', 'boshqa')), 160),
            left(trim(COALESCE(source.row_data->>'title', source.row_data->>'name', '')), 200),
            left(trim(COALESCE(source.row_data->>'price', source.row_data->>'price_text', '')), 120),
            left(trim(COALESCE(source.row_data->>'descr', source.row_data->>'description', '')), 4000),
            left(trim(COALESCE(source.row_data->>'address', '')), 300),
            CASE
                WHEN COALESCE(source.row_data->>'lat', source.row_data->>'latitude', '')
                     ~ '^-?[0-9]+([.][0-9]+)?$'
                THEN COALESCE(source.row_data->>'lat', source.row_data->>'latitude')::double precision
                ELSE NULL
            END,
            CASE
                WHEN COALESCE(source.row_data->>'lng', source.row_data->>'longitude', '')
                     ~ '^-?[0-9]+([.][0-9]+)?$'
                THEN COALESCE(source.row_data->>'lng', source.row_data->>'longitude')::double precision
                ELSE NULL
            END,
            CASE WHEN source.row_data->>'visibility' = 'own' THEN 'own' ELSE 'all' END,
            CASE WHEN source.row_data->>'status' = 'inactive' THEN 'inactive' ELSE 'active' END,
            CASE
                WHEN trim(COALESCE(source.row_data->>'title', source.row_data->>'name', '')) <> ''
                 AND COALESCE(source.row_data->>'cat', source.row_data->>'category', 'boshqa')
                     IN ('uy', 'ish', 'moshina', 'hayvon', 'texnika', 'boshqa')
                THEN 'ready'::review_state
                ELSE 'review_required'::review_state
            END,
            NULL,
            now(),
            now()
        FROM listing_source AS source
        ON CONFLICT (owner_business_account_id, source_record_key) DO UPDATE SET
            category = EXCLUDED.category,
            title = EXCLUDED.title,
            price_text = EXCLUDED.price_text,
            description = EXCLUDED.description,
            address = EXCLUDED.address,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            visibility = EXCLUDED.visibility,
            status = EXCLUDED.status,
            review_state = EXCLUDED.review_state,
            updated_at = now()
    """))

    # Yangi R2 media kalitlarini ham pozitsiyasi bilan birga qayta bog'laymiz.
    op.execute(sa.text(r"""
        WITH relational_media AS (
            SELECT
                resource.account_id,
                record.source_key AS source_record_key,
                substring(field.path from '^/media/([0-9]+)')::integer AS position,
                max(field.value_text) FILTER (
                    WHERE field.path ~ '^/media/[0-9]+/(object_key|file_id|media_url)$'
                ) AS object_key,
                max(field.value_text) FILTER (
                    WHERE field.path ~ '^/media/[0-9]+/type$'
                ) AS media_type
            FROM cabinet_resources AS resource
            JOIN cabinet_records AS record ON record.resource_id = resource.id
            JOIN cabinet_record_fields AS field ON field.record_id = record.id
            WHERE resource.account_type = 'business'
              AND resource.resource = 'listings'
              AND field.path ~ '^/media/[0-9]+/'
            GROUP BY resource.account_id, record.source_key, position
        ),
        fallback_media AS (
            SELECT
                profile.account_id,
                COALESCE(
                    NULLIF(entry.row_data->>'id', ''),
                    'ordinal:' || (entry.ordinality - 1)
                ) AS source_record_key,
                (media.ordinality - 1)::integer AS position,
                COALESCE(
                    media.row_data->>'object_key',
                    media.row_data->>'file_id',
                    media.row_data->>'media_url'
                ) AS object_key,
                media.row_data->>'type' AS media_type
            FROM business_profiles AS profile
            CROSS JOIN LATERAL jsonb_array_elements(
                CASE
                    WHEN jsonb_typeof(
                        COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'listings'
                    ) = 'array'
                    THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'listings'
                    ELSE '[]'::jsonb
                END
            ) WITH ORDINALITY AS entry(row_data, ordinality)
            CROSS JOIN LATERAL jsonb_array_elements(
                CASE
                    WHEN jsonb_typeof(entry.row_data->'media') = 'array'
                    THEN entry.row_data->'media'
                    ELSE '[]'::jsonb
                END
            ) WITH ORDINALITY AS media(row_data, ordinality)
            WHERE NOT EXISTS (
                SELECT 1 FROM cabinet_resources AS resource
                WHERE resource.account_id = profile.account_id
                  AND resource.account_type = 'business'
                  AND resource.resource = 'listings'
            )
        ),
        media_source AS (
            SELECT * FROM relational_media
            UNION ALL
            SELECT * FROM fallback_media
        )
        INSERT INTO listing_media (
            listing_id, media_type, object_key, position,
            migration_state, migration_run_id
        )
        SELECT
            listing.id,
            CASE WHEN source.media_type = 'video' THEN 'video' ELSE 'photo' END,
            left(trim(source.object_key), 1024),
            source.position,
            'copied',
            NULL
        FROM media_source AS source
        JOIN listings AS listing
          ON listing.owner_business_account_id = source.account_id
         AND listing.source_record_key = left(source.source_record_key, 160)
        WHERE trim(COALESCE(source.object_key, '')) <> ''
        ON CONFLICT (listing_id, position) DO UPDATE SET
            media_type = EXCLUDED.media_type,
            object_key = EXCLUDED.object_key,
            migration_state = EXCLUDED.migration_state,
            migration_run_id = listing_media.migration_run_id
    """))

    # Eski `saved` yozuvlaridagi e'lon havolalarini yangi saqlanganlarga o'tkazamiz.
    op.execute(sa.text(f"""
        WITH {SAVED_SOURCE_CTES}
        INSERT INTO listing_saves (
            owner_user_account_id, listing_id, created_at
        )
        SELECT
            source.account_id,
            mapping.target_id,
            CASE
                WHEN COALESCE(source.row_data->>'created_at', '')
                     ~ '^[0-9]{{1,10}}([.][0-9]+)?$'
                THEN to_timestamp((source.row_data->>'created_at')::double precision)
                ELSE now()
            END
        FROM saved_source AS source
        JOIN legacy_id_map AS mapping
          ON mapping.entity_type = 'listing'
         AND mapping.target_id IS NOT NULL
         AND mapping.legacy_id = CASE
             WHEN COALESCE(source.row_data->>'target_id', '') ~ '^[0-9]+$'
             THEN (source.row_data->>'target_id')::bigint
             ELSE NULL
         END
        WHERE COALESCE(
            source.row_data->>'target_kind',
            source.row_data->>'kind',
            ''
        ) = 'listing'
        ON CONFLICT (owner_user_account_id, listing_id) DO NOTHING
    """))


def downgrade() -> None:
    op.drop_index("ix_listing_saves_owner_created", table_name="listing_saves")
    op.drop_table("listing_saves")
    op.drop_index("ix_listings_public_v1656", table_name="listings")
    op.drop_index("uq_listings_business_source", table_name="listings")
    # Eski sxemada migration_run_id majburiy: faqat 0008/live oqimi yaratgan
    # yozuvlarni olib tashlab, Phase 3C importlarini saqlab qolamiz.
    op.execute(sa.text("DELETE FROM listing_media WHERE migration_run_id IS NULL"))
    op.execute(sa.text("DELETE FROM listings WHERE migration_run_id IS NULL"))
    op.alter_column("listing_media", "migration_run_id", nullable=False)
    op.alter_column("listings", "migration_run_id", nullable=False)
    op.drop_column("listings", "source_record_key")
