"""Public katalogni V7 kabinet yozuvlari bilan jonli sinxronlash.

Revision ID: 0007_catalog_live_sync
Revises: 0006_v7_cabinet_records
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_catalog_live_sync"
down_revision = "0006_v7_cabinet_records"
branch_labels = None
depends_on = None


SOURCE_CTES = r"""
record_rows AS (
    SELECT
        resource.account_id,
        resource.resource,
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
      AND resource.resource IN ('item_groups', 'items')
    GROUP BY resource.account_id, resource.resource, record.id, record.source_key
),
relational_groups AS (
    SELECT rows.account_id, profile.name AS owner_name,
           rows.source_key AS source_record_key, rows.row_data
    FROM record_rows AS rows
    JOIN business_profiles AS profile ON profile.account_id = rows.account_id
    WHERE rows.resource = 'item_groups'
),
fallback_groups AS (
    SELECT profile.account_id, profile.name AS owner_name,
           COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality) AS source_record_key,
           entry.row_data
    FROM business_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'item_groups') = 'array'
            THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'item_groups'
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
    WHERE NOT EXISTS (
        SELECT 1 FROM cabinet_resources AS resource
        WHERE resource.account_id = profile.account_id
          AND resource.account_type = 'business'
          AND resource.resource = 'item_groups'
    )
),
group_source AS (
    SELECT * FROM relational_groups
    UNION ALL
    SELECT * FROM fallback_groups
),
relational_items AS (
    SELECT rows.account_id, profile.name AS owner_name,
           rows.source_key AS source_record_key, rows.row_data
    FROM record_rows AS rows
    JOIN business_profiles AS profile ON profile.account_id = rows.account_id
    WHERE rows.resource = 'items'
),
fallback_items AS (
    SELECT profile.account_id, profile.name AS owner_name,
           COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality) AS source_record_key,
           entry.row_data
    FROM business_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'items') = 'array'
            THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'items'
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
    WHERE NOT EXISTS (
        SELECT 1 FROM cabinet_resources AS resource
        WHERE resource.account_id = profile.account_id
          AND resource.account_type = 'business'
          AND resource.resource = 'items'
    )
),
item_source AS (
    SELECT * FROM relational_items
    UNION ALL
    SELECT * FROM fallback_items
)
"""


def upgrade() -> None:
    op.add_column(
        "catalog_groups",
        sa.Column("source_record_key", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "catalog_items",
        sa.Column("source_record_key", sa.String(length=160), nullable=True),
    )
    op.alter_column(
        "catalog_groups",
        "migration_run_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.alter_column(
        "catalog_items",
        "migration_run_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.create_index(
        "ix_catalog_groups_live_source",
        "catalog_groups",
        ["business_account_id", "source_record_key"],
        unique=True,
    )
    op.create_index(
        "ix_catalog_items_live_source",
        "catalog_items",
        ["business_account_id", "source_record_key"],
        unique=True,
    )
    op.create_index(
        "ix_catalog_items_catalog_group_id",
        "catalog_items",
        ["catalog_group_id"],
        unique=False,
    )

    # Avvalgi Phase 3C importini aynan o‘sha kabinet yozuvi bilan bog‘laymiz.
    op.execute(sa.text(f"""
        WITH {SOURCE_CTES}, mapped_group_source AS (
            SELECT source.account_id, source.source_record_key, mapping.target_id
            FROM group_source AS source
            JOIN legacy_id_map AS mapping
              ON mapping.entity_type = 'catalog_group'
             AND mapping.legacy_id = CASE
                 WHEN source.source_record_key ~ '^[0-9]+$'
                 THEN source.source_record_key::bigint
                 ELSE NULL
             END
        )
        UPDATE catalog_groups AS target
        SET source_record_key = (
            SELECT mapped.source_record_key
            FROM mapped_group_source AS mapped
            WHERE mapped.target_id = target.id
              AND mapped.account_id = target.business_account_id
            LIMIT 1
        )
        WHERE target.source_record_key IS NULL
          AND EXISTS (
              SELECT 1 FROM mapped_group_source AS mapped
              WHERE mapped.target_id = target.id
                AND mapped.account_id = target.business_account_id
          )
    """))

    op.execute(sa.text(f"""
        WITH {SOURCE_CTES}
        INSERT INTO catalog_groups (
            business_account_id, source_record_key, owner_name_snapshot,
            name, kind, status, review_state, migration_run_id,
            created_at, updated_at
        )
        SELECT
            source.account_id,
            left(source.source_record_key, 160),
            left(trim(COALESCE(source.owner_name, '')), 160),
            left(trim(COALESCE(source.row_data->>'name', source.row_data->>'title', '')), 160),
            CASE
                WHEN lower(COALESCE(source.row_data->>'kind', source.row_data->>'item_type', source.row_data->>'type', '')) = 'service'
                THEN 'service'
                ELSE 'product'
            END,
            left(COALESCE(NULLIF(trim(source.row_data->>'status'), ''), 'active'), 20),
            CASE
                WHEN trim(COALESCE(source.row_data->>'name', source.row_data->>'title', '')) <> ''
                 AND lower(COALESCE(source.row_data->>'kind', source.row_data->>'item_type', source.row_data->>'type', '')) IN ('', 'product', 'service')
                THEN 'ready'::review_state
                ELSE 'review_required'::review_state
            END,
            NULL,
            now(),
            now()
        FROM group_source AS source
        ON CONFLICT (business_account_id, source_record_key) DO UPDATE SET
            owner_name_snapshot = EXCLUDED.owner_name_snapshot,
            name = EXCLUDED.name,
            kind = EXCLUDED.kind,
            status = EXCLUDED.status,
            review_state = EXCLUDED.review_state,
            updated_at = now()
    """))

    op.execute(sa.text(f"""
        WITH {SOURCE_CTES}, mapped_item_source AS (
            SELECT source.account_id, source.source_record_key, mapping.target_id
            FROM item_source AS source
            JOIN legacy_id_map AS mapping
              ON mapping.entity_type = 'catalog_item'
             AND mapping.legacy_id = CASE
                 WHEN source.source_record_key ~ '^[0-9]+$'
                 THEN source.source_record_key::bigint
                 ELSE NULL
             END
        )
        UPDATE catalog_items AS target
        SET source_record_key = (
            SELECT mapped.source_record_key
            FROM mapped_item_source AS mapped
            WHERE mapped.target_id = target.id
              AND mapped.account_id = target.business_account_id
            LIMIT 1
        )
        WHERE target.source_record_key IS NULL
          AND EXISTS (
              SELECT 1 FROM mapped_item_source AS mapped
              WHERE mapped.target_id = target.id
                AND mapped.account_id = target.business_account_id
          )
    """))

    op.execute(sa.text(f"""
        WITH {SOURCE_CTES}
        INSERT INTO catalog_items (
            business_account_id, source_record_key, catalog_group_id,
            owner_name_snapshot, name, price_text, note, kind,
            queue_enabled, image_object_key, status, owner_state,
            review_state, migration_run_id, created_at, updated_at
        )
        SELECT
            source.account_id,
            left(source.source_record_key, 160),
            linked_group.id,
            left(trim(COALESCE(source.owner_name, '')), 160),
            left(trim(COALESCE(source.row_data->>'name', source.row_data->>'title', '')), 160),
            left(trim(COALESCE(source.row_data->>'price', source.row_data->>'price_text', source.row_data->>'price_amount', '')), 120),
            left(trim(COALESCE(source.row_data->>'note', source.row_data->>'description', source.row_data->>'descr', '')), 2000),
            CASE
                WHEN lower(COALESCE(source.row_data->>'kind', source.row_data->>'item_type', source.row_data->>'type', '')) = 'service'
                THEN 'service'
                ELSE 'product'
            END,
            lower(COALESCE(source.row_data->>'queue_enabled', '')) IN ('1', 'true', 'on', 'yes'),
            left(trim(COALESCE(source.row_data->>'image_object_key', source.row_data->>'photo_object_key', '')), 1024),
            left(COALESCE(NULLIF(trim(source.row_data->>'status'), ''), 'active'), 20),
            'linked'::owner_state,
            CASE
                WHEN trim(COALESCE(source.row_data->>'name', source.row_data->>'title', '')) <> ''
                 AND lower(COALESCE(source.row_data->>'kind', source.row_data->>'item_type', source.row_data->>'type', '')) IN ('', 'product', 'service')
                THEN 'ready'::review_state
                ELSE 'review_required'::review_state
            END,
            NULL,
            now(),
            now()
        FROM item_source AS source
        LEFT JOIN catalog_groups AS linked_group
          ON linked_group.business_account_id = source.account_id
         AND linked_group.source_record_key = COALESCE(
             NULLIF(source.row_data->>'group_id', ''),
             NULLIF(source.row_data->>'item_group_id', ''),
             NULLIF(source.row_data->>'group', '')
         )
        ON CONFLICT (business_account_id, source_record_key) DO UPDATE SET
            catalog_group_id = EXCLUDED.catalog_group_id,
            owner_name_snapshot = EXCLUDED.owner_name_snapshot,
            name = EXCLUDED.name,
            price_text = EXCLUDED.price_text,
            note = EXCLUDED.note,
            kind = EXCLUDED.kind,
            queue_enabled = EXCLUDED.queue_enabled,
            image_object_key = CASE
                WHEN EXCLUDED.image_object_key <> '' THEN EXCLUDED.image_object_key
                ELSE catalog_items.image_object_key
            END,
            status = EXCLUDED.status,
            owner_state = EXCLUDED.owner_state,
            review_state = EXCLUDED.review_state,
            updated_at = now()
    """))

    # Kabinetda allaqachon o‘chirilgan, lekin eski snapshotda qolgan yozuvlar
    # public qidiruvda qayta ko‘rinmasligi kerak.
    op.execute(sa.text(f"""
        WITH {SOURCE_CTES}, mapped_items AS (
            SELECT target.id, target.business_account_id,
                   COALESCE(target.source_record_key, mapping.legacy_id::text) AS source_record_key
            FROM catalog_items AS target
            LEFT JOIN legacy_id_map AS mapping
              ON mapping.entity_type = 'catalog_item'
             AND mapping.target_id = target.id
            WHERE target.business_account_id IS NOT NULL
              AND (target.source_record_key IS NOT NULL OR mapping.legacy_id IS NOT NULL)
        )
        DELETE FROM catalog_items AS target
        WHERE target.id IN (
            SELECT mapped.id
            FROM mapped_items AS mapped
            WHERE NOT EXISTS (
                SELECT 1 FROM item_source AS source
                WHERE source.account_id = mapped.business_account_id
                  AND source.source_record_key = mapped.source_record_key
            )
          )
    """))

    op.execute(sa.text(f"""
        WITH {SOURCE_CTES}, mapped_groups AS (
            SELECT target.id, target.business_account_id,
                   COALESCE(target.source_record_key, mapping.legacy_id::text) AS source_record_key
            FROM catalog_groups AS target
            LEFT JOIN legacy_id_map AS mapping
              ON mapping.entity_type = 'catalog_group'
             AND mapping.target_id = target.id
            WHERE target.business_account_id IS NOT NULL
              AND (target.source_record_key IS NOT NULL OR mapping.legacy_id IS NOT NULL)
        )
        DELETE FROM catalog_groups AS target
        WHERE target.id IN (
            SELECT mapped.id
            FROM mapped_groups AS mapped
            WHERE NOT EXISTS (
                SELECT 1 FROM group_source AS source
                WHERE source.account_id = mapped.business_account_id
                  AND source.source_record_key = mapped.source_record_key
            )
          )
    """))


def downgrade() -> None:
    # Eski sxema migration_run_id talab qiladi; faqat live-sync yaratgan
    # yozuvlar olib tashlanadi, tarixiy Phase 3C importi saqlanadi.
    op.execute(sa.text("DELETE FROM catalog_items WHERE migration_run_id IS NULL"))
    op.execute(sa.text("DELETE FROM catalog_groups WHERE migration_run_id IS NULL"))
    op.drop_index("ix_catalog_items_catalog_group_id", table_name="catalog_items")
    op.drop_index("ix_catalog_items_live_source", table_name="catalog_items")
    op.drop_index("ix_catalog_groups_live_source", table_name="catalog_groups")
    op.alter_column(
        "catalog_items",
        "migration_run_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.alter_column(
        "catalog_groups",
        "migration_run_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.drop_column("catalog_items", "source_record_key")
    op.drop_column("catalog_groups", "source_record_key")
