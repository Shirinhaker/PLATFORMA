"""v1656 bildirishnoma, push va e'lon filtrlari domenini yakunlash.

Revision ID: 0033_notifications_v1656
Revises: 0032_reviews
"""

from alembic import op
import sqlalchemy as sa


revision = "0033_notifications_v1656"
down_revision = "0032_reviews"
branch_labels = None
depends_on = None


RESOURCE_ROWS = r"""
resource_rows AS (
    SELECT
        resource.account_id,
        resource.account_type::text AS account_type,
        resource.resource,
        record.source_key,
        record.ordinal,
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
    WHERE resource.resource IN ('push_preferences', 'notify_filters')
    GROUP BY
        resource.account_id,
        resource.account_type,
        resource.resource,
        record.id,
        record.source_key,
        record.ordinal
),
payload_rows AS (
    SELECT
        profile.account_id,
        'user'::text AS account_type,
        source.resource,
        COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality),
        entry.ordinality::integer,
        entry.row_data,
        1 AS priority
    FROM user_profiles AS profile
    CROSS JOIN LATERAL (VALUES ('push_preferences'), ('notify_filters'))
        AS source(resource)
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(
            COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)
                -> source.resource
        ) = 'array'
        THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)
                -> source.resource
        ELSE '[]'::jsonb END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
    UNION ALL
    SELECT
        profile.account_id,
        'business'::text,
        source.resource,
        COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality),
        entry.ordinality::integer,
        entry.row_data,
        1
    FROM business_profiles AS profile
    CROSS JOIN LATERAL (VALUES ('push_preferences'), ('notify_filters'))
        AS source(resource)
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(
            COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)
                -> source.resource
        ) = 'array'
        THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)
                -> source.resource
        ELSE '[]'::jsonb END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
),
all_rows AS (
    SELECT * FROM resource_rows
    UNION ALL SELECT * FROM payload_rows
)
"""


def upgrade() -> None:
    op.add_column("notifications", sa.Column("listing_id", sa.BigInteger()))
    op.add_column("notifications", sa.Column("dining_order_id", sa.BigInteger()))
    op.add_column("notifications", sa.Column("medical_queue_id", sa.BigInteger()))
    op.add_column("notifications", sa.Column("ride_id", sa.BigInteger()))
    op.add_column("notifications", sa.Column("target_staff_id", sa.BigInteger()))
    op.add_column(
        "notifications",
        sa.Column(
            "target_permission",
            sa.String(length=80),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column("notifications", sa.Column("resolved_at", sa.BigInteger()))
    op.create_foreign_key(
        "fk_notifications_listing_id",
        "notifications",
        "listings",
        ["listing_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_notifications_owner_actionable",
        "notifications",
        ["account_id", "account_type", "created_at"],
        postgresql_where=sa.text(
            "requires_action = true AND is_read = false AND resolved_at IS NULL"
        ),
    )
    op.create_index(
        "ix_notifications_owner_listing",
        "notifications",
        ["account_id", "account_type", "listing_id"],
        postgresql_where=sa.text("listing_id IS NOT NULL"),
    )

    # 0011 payloadida qolgan deep-link va xodimga yo'naltirish maydonlari
    # typed ustunlarga ko'chadi. Queue/dining legacy IDlari yangi relatsion
    # jadvallardagi IDga aylantiriladi.
    op.execute(sa.text(r"""
        UPDATE notifications AS notification
        SET listing_id = COALESCE(
                CASE WHEN COALESCE(notification.payload->>'listing_id', '')
                               ~ '^[0-9]+$'
                     THEN (SELECT target.id FROM listings AS target
                           WHERE target.id =
                               (notification.payload->>'listing_id')::bigint
                           LIMIT 1) END,
                (SELECT target.id FROM listings AS target
                 WHERE target.public_id =
                     NULLIF(notification.payload->>'listing_public_id', '')
                 LIMIT 1)
            ),
            resolved_at = CASE
                WHEN COALESCE(notification.payload->>'resolved_at', '') ~ '^[0-9]+$'
                THEN (notification.payload->>'resolved_at')::bigint ELSE NULL END,
            ride_id = CASE
                WHEN COALESCE(notification.payload->>'ride_id', '') ~ '^[0-9]+$'
                THEN (notification.payload->>'ride_id')::bigint ELSE NULL END,
            target_staff_id = CASE
                WHEN COALESCE(notification.payload->>'target_staff_id', '') ~ '^[0-9]+$'
                THEN (notification.payload->>'target_staff_id')::bigint ELSE NULL END,
            target_permission = left(COALESCE(
                NULLIF(notification.payload->>'target_permission', ''),
                notification.payload->>'target_perm',
                ''
            ), 80),
            dining_order_id = COALESCE(
                CASE WHEN COALESCE(notification.payload->>'dining_order_id', '')
                               ~ '^[0-9]+$'
                     THEN (SELECT target.id FROM dining_orders AS target
                           WHERE target.id =
                               (notification.payload->>'dining_order_id')::bigint
                           LIMIT 1) END,
                CASE WHEN COALESCE(notification.payload->>'dining_order_id', '')
                               ~ '^[0-9]+$'
                     THEN (SELECT target.id FROM dining_orders AS target
                           WHERE target.business_account_id = notification.account_id
                             AND target.legacy_source_id =
                               (notification.payload->>'dining_order_id')::bigint
                           LIMIT 1) END
            ),
            medical_queue_id = COALESCE(
                CASE WHEN COALESCE(notification.payload->>'medical_queue_id', '')
                               ~ '^[0-9]+$'
                     THEN (SELECT target.id FROM queue_entries AS target
                           WHERE target.id =
                               (notification.payload->>'medical_queue_id')::bigint
                           LIMIT 1) END,
                CASE WHEN COALESCE(notification.payload->>'medical_queue_id', '')
                               ~ '^[0-9]+$'
                     THEN (SELECT target.id FROM queue_entries AS target
                           WHERE target.legacy_source_id =
                               (notification.payload->>'medical_queue_id')::bigint
                             AND (
                                 target.customer_account_id = notification.account_id
                                 OR target.business_account_id = notification.account_id
                             )
                           LIMIT 1) END
            )
    """))

    op.create_table(
        "notification_preferences",
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("account_type", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "orders_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "account_type IN ('user', 'business')",
            name="ck_notification_preferences_account_type",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("account_id", "account_type"),
    )

    op.create_table(
        "notification_filters",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("account_type", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("region", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("district", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("price_min", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("price_max", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("keyword", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "account_type IN ('user', 'business')",
            name="ck_notification_filters_account_type",
        ),
        sa.CheckConstraint(
            "category IN ('uy', 'ish', 'moshina', 'hayvon', 'texnika', 'boshqa')",
            name="ck_notification_filters_category",
        ),
        sa.CheckConstraint(
            "price_min >= 0 AND price_max >= 0",
            name="ck_notification_filters_prices",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_notification_filters_match",
        "notification_filters",
        ["category", "account_id"],
    )
    op.create_index(
        "ix_notification_filters_owner",
        "notification_filters",
        ["account_id", "account_type", "id"],
    )
    op.create_index(
        "uq_notification_filters_legacy_source",
        "notification_filters",
        ["account_id", "account_type", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )

    op.create_table(
        "push_devices",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("token", sa.String(length=4096), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("device_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("app_version", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.Column("last_seen_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "platform IN ('android', 'ios', 'web')",
            name="ck_push_devices_platform",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("token", name="uq_push_devices_token"),
    )
    op.create_index(
        "ix_push_devices_owner_enabled",
        "push_devices",
        ["account_id", "enabled"],
    )

    op.create_table(
        "push_outbox",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("notification_id", sa.BigInteger(), nullable=False),
        sa.Column("device_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("available_at", sa.BigInteger(), nullable=False),
        sa.Column("last_attempt_at", sa.BigInteger()),
        sa.Column("sent_at", sa.BigInteger()),
        sa.CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed')",
            name="ck_push_outbox_status",
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"], ["notifications.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["device_id"], ["push_devices.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "notification_id",
            "device_id",
            name="uq_push_outbox_notification_device",
        ),
    )
    op.create_index(
        "ix_push_outbox_status_available",
        "push_outbox",
        ["status", "available_at"],
    )

    op.execute(sa.text(f"""
        WITH {RESOURCE_ROWS},
        preference_source AS (
            SELECT DISTINCT ON (account_id, account_type)
                account_id, account_type, row_data
            FROM all_rows
            WHERE resource = 'push_preferences'
              AND account_type IN ('user', 'business')
            ORDER BY account_id, account_type, priority, ordinal DESC
        )
        INSERT INTO notification_preferences (
            account_id, account_type, enabled, orders_enabled, updated_at
        )
        SELECT
            account_id,
            account_type,
            lower(COALESCE(row_data->>'enabled', 'true'))
                IN ('1', 'true', 'yes', 'on'),
            lower(COALESCE(row_data->>'orders_enabled', 'true'))
                IN ('1', 'true', 'yes', 'on'),
            CASE WHEN COALESCE(row_data->>'updated_at', '') ~ '^[0-9]+$'
                 THEN (row_data->>'updated_at')::bigint
                 ELSE extract(epoch FROM now())::bigint END
        FROM preference_source
        ON CONFLICT (account_id, account_type) DO NOTHING
    """))

    op.execute(sa.text(f"""
        WITH {RESOURCE_ROWS},
        filter_source AS (
            SELECT DISTINCT ON (account_id, account_type, source_key)
                account_id, account_type, source_key, row_data, priority, ordinal
            FROM all_rows
            WHERE resource = 'notify_filters'
              AND account_type IN ('user', 'business')
              AND COALESCE(row_data->>'cat', '')
                    IN ('uy', 'ish', 'moshina', 'hayvon', 'texnika', 'boshqa')
            ORDER BY account_id, account_type, source_key, priority, ordinal
        )
        INSERT INTO notification_filters (
            legacy_source_id, account_id, account_type, category, region,
            district, price_min, price_max, keyword, created_at
        )
        SELECT
            CASE WHEN COALESCE(NULLIF(row_data->>'id', ''), source_key, '')
                           ~ '^[0-9]+$'
                 THEN COALESCE(NULLIF(row_data->>'id', ''), source_key)::bigint
                 ELSE -abs(hashtext(
                     account_id::text || ':' || account_type || ':'
                     || COALESCE(source_key, 'ordinal:' || ordinal::text)
                 ))::bigint - 1 END,
            account_id,
            account_type,
            row_data->>'cat',
            left(COALESCE(row_data->>'region', ''), 120),
            left(COALESCE(row_data->>'district', ''), 120),
            CASE WHEN COALESCE(row_data->>'price_min', '') ~ '^[0-9]+$'
                 THEN (row_data->>'price_min')::bigint ELSE 0 END,
            CASE WHEN COALESCE(row_data->>'price_max', '') ~ '^[0-9]+$'
                 THEN (row_data->>'price_max')::bigint ELSE 0 END,
            left(COALESCE(row_data->>'keyword', ''), 160),
            CASE WHEN COALESCE(row_data->>'created_at', '') ~ '^[0-9]+$'
                 THEN (row_data->>'created_at')::bigint
                 ELSE extract(epoch FROM now())::bigint END
        FROM filter_source
        ON CONFLICT DO NOTHING
    """))


def downgrade() -> None:
    op.drop_index("ix_push_outbox_status_available", table_name="push_outbox")
    op.drop_table("push_outbox")
    op.drop_index("ix_push_devices_owner_enabled", table_name="push_devices")
    op.drop_table("push_devices")
    op.drop_index(
        "uq_notification_filters_legacy_source",
        table_name="notification_filters",
    )
    op.drop_index("ix_notification_filters_owner", table_name="notification_filters")
    op.drop_index("ix_notification_filters_match", table_name="notification_filters")
    op.drop_table("notification_filters")
    op.drop_table("notification_preferences")
    op.drop_index("ix_notifications_owner_listing", table_name="notifications")
    op.drop_index("ix_notifications_owner_actionable", table_name="notifications")
    op.drop_constraint(
        "fk_notifications_listing_id",
        "notifications",
        type_="foreignkey",
    )
    op.drop_column("notifications", "resolved_at")
    op.drop_column("notifications", "target_permission")
    op.drop_column("notifications", "target_staff_id")
    op.drop_column("notifications", "ride_id")
    op.drop_column("notifications", "medical_queue_id")
    op.drop_column("notifications", "dining_order_id")
    op.drop_column("notifications", "listing_id")
