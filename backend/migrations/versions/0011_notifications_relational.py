"""Bildirishnomalarni profil JSON'idan alohida relatsion jadvalga ko'chirish.

Revision ID: 0011_notifications_relational
Revises: 0010_public_id_indexed_lookup
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_notifications_relational"
down_revision = "0010_public_id_indexed_lookup"
branch_labels = None
depends_on = None


NOTIFICATION_SOURCE_CTES = r"""
relational_notification_rows AS (
    SELECT
        resource.account_id,
        resource.account_type::text AS account_type,
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
    WHERE resource.resource = 'notifications'
    GROUP BY
        resource.account_id,
        resource.account_type,
        record.id,
        record.source_key,
        record.ordinal
),
payload_notification_rows AS (
    SELECT
        profile.account_id,
        'user'::text AS account_type,
        COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality) AS source_key,
        entry.ordinality::integer AS ordinal,
        entry.row_data,
        1 AS priority
    FROM user_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(
                COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'notifications'
            ) = 'array'
            THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'notifications'
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
    UNION ALL
    SELECT
        profile.account_id,
        'business'::text,
        COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality),
        entry.ordinality::integer,
        entry.row_data,
        1
    FROM business_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(
                COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'notifications'
            ) = 'array'
            THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'notifications'
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
),
all_notification_rows AS (
    SELECT * FROM relational_notification_rows
    UNION ALL
    SELECT * FROM payload_notification_rows
),
notification_source AS (
    SELECT DISTINCT ON (account_id, account_type, event_key)
        account_id,
        account_type,
        event_key,
        row_data
    FROM (
        SELECT
            account_id,
            account_type,
            COALESCE(
                NULLIF(row_data->>'event_key', ''),
                'legacy:' || account_type || ':' || account_id || ':' || source_key
            ) AS event_key,
            row_data,
            priority,
            ordinal
        FROM all_notification_rows
        WHERE account_type IN ('user', 'business')
    ) AS candidates
    ORDER BY account_id, account_type, event_key, priority, ordinal
)
"""


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("account_type", sa.String(length=16), nullable=False),
        sa.Column("event_key", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("order_id", sa.BigInteger()),
        sa.Column("action_type", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("requires_action", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("read_at", sa.BigInteger()),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.CheckConstraint(
            "account_type IN ('user', 'business')",
            name="ck_notifications_account_type",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "uq_notifications_owner_event",
        "notifications",
        ["account_id", "account_type", "event_key"],
        unique=True,
    )
    op.create_index(
        "ix_notifications_owner_created",
        "notifications",
        ["account_id", "account_type", "created_at", "id"],
    )
    op.create_index(
        "ix_notifications_owner_unread",
        "notifications",
        ["account_id", "account_type", "created_at"],
        postgresql_where=sa.text("is_read = false"),
    )
    op.create_index(
        "ix_notifications_owner_order",
        "notifications",
        ["account_id", "account_type", "order_id"],
        postgresql_where=sa.text("order_id IS NOT NULL"),
    )

    connection = op.get_bind()
    connection.execute(sa.text(
        f"""
        WITH {NOTIFICATION_SOURCE_CTES}
        INSERT INTO notifications (
            account_id,
            account_type,
            event_key,
            title,
            body,
            order_id,
            action_type,
            requires_action,
            is_read,
            created_at,
            read_at,
            payload
        )
        SELECT
            account_id,
            account_type,
            left(event_key, 200),
            left(COALESCE(row_data->>'title', ''), 300),
            COALESCE(row_data->>'body', row_data->>'message', row_data->>'text', ''),
            CASE
                WHEN event_key LIKE 'order:%'
                THEN COALESCE(direct_order.id, legacy_order.id)
                ELSE COALESCE(legacy_order.id, direct_order.id)
            END,
            left(COALESCE(row_data->>'action_type', ''), 80),
            lower(COALESCE(row_data->>'requires_action', '0')) IN ('1', 'true', 'yes', 'on'),
            lower(COALESCE(row_data->>'is_read', '0')) IN ('1', 'true', 'yes', 'on'),
            CASE
                WHEN COALESCE(row_data->>'created_at', '') ~ '^[0-9]+$'
                THEN (row_data->>'created_at')::bigint
                ELSE extract(epoch FROM now())::bigint
            END,
            CASE
                WHEN COALESCE(row_data->>'read_at', '') ~ '^[0-9]+$'
                THEN (row_data->>'read_at')::bigint
                ELSE NULL
            END,
            row_data - ARRAY[
                'id', 'event_key', 'title', 'body',
                'order_id', 'action_type', 'requires_action', 'is_read',
                'created_at', 'read_at'
            ]::text[]
        FROM notification_source
        LEFT JOIN orders AS direct_order
          ON direct_order.id = CASE
                WHEN COALESCE(
                    notification_source.row_data->>'order_id', ''
                ) ~ '^[0-9]+$'
                THEN (notification_source.row_data->>'order_id')::bigint
                ELSE NULL
             END
        LEFT JOIN orders AS legacy_order
          ON direct_order.id IS NULL
         AND legacy_order.legacy_source_id = CASE
                WHEN COALESCE(
                    notification_source.row_data->>'order_id', ''
                ) ~ '^[0-9]+$'
                THEN (notification_source.row_data->>'order_id')::bigint
                ELSE NULL
             END
        ON CONFLICT (account_id, account_type, event_key) DO NOTHING
        """
    ))


def downgrade() -> None:
    op.drop_index("ix_notifications_owner_order", table_name="notifications")
    op.drop_index("ix_notifications_owner_unread", table_name="notifications")
    op.drop_index("ix_notifications_owner_created", table_name="notifications")
    op.drop_index("uq_notifications_owner_event", table_name="notifications")
    op.drop_table("notifications")
