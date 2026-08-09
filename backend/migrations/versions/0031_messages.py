"""v1656 umumiy Suhbatlar domeni.

Revision ID: 0031_messages
Revises: 0030_stories
"""

from alembic import op
import sqlalchemy as sa


revision = "0031_messages"
down_revision = "0030_stories"
branch_labels = None
depends_on = None


# Relatsion kabinet yozuvi birinchi manba, eski profile JSON esa fallback.
# Bir xabar user va business profillarida takrorlangan bo‘lishi mumkin; legacy id
# bo‘yicha DISTINCT ON va partial unique indeks backfillni idempotent qiladi.
MESSAGE_SOURCE_CTES = r"""
relational_message_rows AS (
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
    WHERE resource.resource = 'messages'
    GROUP BY record.id, record.source_key
),
payload_message_rows AS (
    SELECT
        COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality),
        entry.row_data,
        1 AS priority
    FROM user_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(
                COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'messages'
            ) = 'array'
            THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'messages'
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
    UNION ALL
    SELECT
        COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality),
        entry.row_data,
        1
    FROM business_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(
                COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'messages'
            ) = 'array'
            THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)->'messages'
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
),
all_message_rows AS (
    SELECT * FROM relational_message_rows
    UNION ALL
    SELECT * FROM payload_message_rows
),
message_source AS (
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
        FROM all_message_rows
    ) AS eligible
    WHERE eligible.legacy_source_id IS NOT NULL
      AND COALESCE(row_data->>'sender_kind', 'user') IN ('user', 'business')
      AND COALESCE(row_data->>'receiver_kind', 'user') IN ('user', 'business')
    ORDER BY eligible.legacy_source_id, eligible.priority
),
resolved_message_source AS (
    SELECT
        source.legacy_source_id,
        source.row_data,
        sender_map.target_id::bigint AS sender_account_id,
        receiver_map.target_id::bigint AS receiver_account_id
    FROM message_source AS source
    JOIN legacy_id_map AS sender_map
      ON sender_map.entity_type = CASE
           WHEN COALESCE(source.row_data->>'sender_kind', 'user') = 'business'
           THEN 'business_account' ELSE 'user_account' END
     AND sender_map.legacy_id = CASE
           WHEN COALESCE(
                  NULLIF(source.row_data->>'sender_actor_id', ''),
                  NULLIF(source.row_data->>'sender_id', ''),
                  ''
                ) ~ '^[0-9]+$'
           THEN COALESCE(
               NULLIF(source.row_data->>'sender_actor_id', ''),
               NULLIF(source.row_data->>'sender_id', '')
           )::bigint
           ELSE -1 END
     AND sender_map.target_id IS NOT NULL
    JOIN legacy_id_map AS receiver_map
      ON receiver_map.entity_type = CASE
           WHEN COALESCE(source.row_data->>'receiver_kind', 'user') = 'business'
           THEN 'business_account' ELSE 'user_account' END
     AND receiver_map.legacy_id = CASE
           WHEN COALESCE(
                  NULLIF(source.row_data->>'receiver_actor_id', ''),
                  NULLIF(source.row_data->>'receiver_id', ''),
                  ''
                ) ~ '^[0-9]+$'
           THEN COALESCE(
               NULLIF(source.row_data->>'receiver_actor_id', ''),
               NULLIF(source.row_data->>'receiver_id', '')
           )::bigint
           ELSE -1 END
     AND receiver_map.target_id IS NOT NULL
    WHERE COALESCE(
            NULLIF(source.row_data->>'sender_actor_id', ''),
            NULLIF(source.row_data->>'sender_id', ''),
            ''
          ) ~ '^[0-9]+$'
      AND COALESCE(
            NULLIF(source.row_data->>'receiver_actor_id', ''),
            NULLIF(source.row_data->>'receiver_id', ''),
            ''
          ) ~ '^[0-9]+$'
      AND sender_map.target_id <> receiver_map.target_id
)
"""


def upgrade() -> None:
    op.create_table(
        "message_conversations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("low_account_id", sa.BigInteger(), nullable=False),
        sa.Column("high_account_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["low_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["high_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "low_account_id < high_account_id",
            name="ck_message_conversations_canonical_pair",
        ),
    )
    op.create_index(
        "uq_message_conversations_pair",
        "message_conversations",
        ["low_account_id", "high_account_id"],
        unique=True,
    )
    op.create_index(
        "ix_message_conversations_low_updated",
        "message_conversations",
        ["low_account_id", "updated_at"],
    )
    op.create_index(
        "ix_message_conversations_high_updated",
        "message_conversations",
        ["high_account_id", "updated_at"],
    )

    op.create_table(
        "message_conversation_members",
        sa.Column("conversation_id", sa.BigInteger(), primary_key=True),
        sa.Column("account_id", sa.BigInteger(), primary_key=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["message_conversations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_message_members_account_conversation",
        "message_conversation_members",
        ["account_id", "conversation_id"],
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("sender_account_id", sa.BigInteger(), nullable=False),
        sa.Column("receiver_account_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "media_type", sa.String(length=20), nullable=False,
            server_default="text",
        ),
        sa.Column(
            "media_object_key", sa.String(length=1024), nullable=False,
            server_default="",
        ),
        sa.Column(
            "legacy_media_url", sa.String(length=2048), nullable=False,
            server_default="",
        ),
        sa.Column(
            "file_name", sa.String(length=255), nullable=False,
            server_default="",
        ),
        sa.Column("reply_to_id", sa.BigInteger()),
        sa.Column("edited_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["message_conversations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sender_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["receiver_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reply_to_id"], ["messages.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "sender_account_id <> receiver_account_id",
            name="ck_messages_distinct_participants",
        ),
        sa.CheckConstraint(
            "media_type IN ('text', 'photo')",
            name="ck_messages_media_type",
        ),
    )
    op.create_index(
        "ix_message_conversation_member",
        "messages",
        ["conversation_id", "created_at", "id"],
    )
    op.create_index(
        "ix_messages_sender", "messages", ["sender_account_id", "created_at"]
    )
    op.create_index(
        "ix_messages_receiver",
        "messages",
        ["receiver_account_id", "created_at"],
    )
    op.create_index("ix_messages_reply_to", "messages", ["reply_to_id"])
    op.create_index(
        "ix_messages_receiver_unread",
        "messages",
        ["receiver_account_id", "conversation_id", "created_at"],
        postgresql_where=sa.text("read_at IS NULL"),
    )
    op.create_index(
        "uq_messages_legacy_source",
        "messages",
        ["legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )

    op.execute(sa.text(
        "WITH " + MESSAGE_SOURCE_CTES + r"""
        INSERT INTO message_conversations(
            low_account_id, high_account_id, created_at, updated_at
        )
        SELECT
            LEAST(sender_account_id, receiver_account_id),
            GREATEST(sender_account_id, receiver_account_id),
            MIN(
                CASE WHEN COALESCE(row_data->>'created_at', '')
                               ~ '^[0-9]+([.][0-9]+)?$'
                     THEN to_timestamp((row_data->>'created_at')::double precision)
                     ELSE now() END
            ),
            MAX(
                CASE WHEN COALESCE(row_data->>'created_at', '')
                               ~ '^[0-9]+([.][0-9]+)?$'
                     THEN to_timestamp((row_data->>'created_at')::double precision)
                     ELSE now() END
            )
        FROM resolved_message_source
        GROUP BY
            LEAST(sender_account_id, receiver_account_id),
            GREATEST(sender_account_id, receiver_account_id)
        ON CONFLICT (low_account_id, high_account_id) DO NOTHING
        """
    ))
    op.execute(sa.text(r"""
        INSERT INTO message_conversation_members(
            conversation_id, account_id, joined_at
        )
        SELECT conversation.id, member.account_id, conversation.created_at
        FROM message_conversations AS conversation
        CROSS JOIN LATERAL (
            VALUES (conversation.low_account_id), (conversation.high_account_id)
        ) AS member(account_id)
        ON CONFLICT (conversation_id, account_id) DO NOTHING
    """))
    op.execute(sa.text(
        "WITH " + MESSAGE_SOURCE_CTES + r"""
        INSERT INTO messages(
            legacy_source_id, conversation_id,
            sender_account_id, receiver_account_id,
            text, media_type, media_object_key, legacy_media_url, file_name,
            reply_to_id, edited_at, deleted_at, read_at, is_deleted, created_at
        )
        SELECT
            source.legacy_source_id,
            conversation.id,
            source.sender_account_id,
            source.receiver_account_id,
            CASE
                WHEN lower(COALESCE(source.row_data->>'is_deleted', '0'))
                     IN ('1', 'true', 'yes') THEN ''
                ELSE left(COALESCE(source.row_data->>'text', ''), 2000)
            END,
            CASE WHEN source.row_data->>'media_type' = 'photo'
                 THEN 'photo' ELSE 'text' END,
            left(COALESCE(source.row_data->>'media_object_key', ''), 1024),
            left(COALESCE(source.row_data->>'media_url', ''), 2048),
            left(COALESCE(source.row_data->>'file_name', ''), 255),
            NULL,
            CASE WHEN COALESCE(source.row_data->>'edited_at', '') ~ '^[0-9]+$'
                       AND (source.row_data->>'edited_at')::bigint > 0
                 THEN to_timestamp((source.row_data->>'edited_at')::double precision)
                 ELSE NULL END,
            CASE WHEN COALESCE(source.row_data->>'deleted_at', '') ~ '^[0-9]+$'
                       AND (source.row_data->>'deleted_at')::bigint > 0
                 THEN to_timestamp((source.row_data->>'deleted_at')::double precision)
                 ELSE NULL END,
            CASE WHEN lower(COALESCE(source.row_data->>'is_read', '0'))
                           IN ('1', 'true', 'yes')
                 THEN CASE WHEN COALESCE(source.row_data->>'created_at', '')
                                      ~ '^[0-9]+([.][0-9]+)?$'
                                THEN to_timestamp(
                                    (source.row_data->>'created_at')::double precision
                                )
                                ELSE now() END
                 ELSE NULL END,
            lower(COALESCE(source.row_data->>'is_deleted', '0'))
                IN ('1', 'true', 'yes'),
            CASE WHEN COALESCE(source.row_data->>'created_at', '')
                           ~ '^[0-9]+([.][0-9]+)?$'
                 THEN to_timestamp(
                     (source.row_data->>'created_at')::double precision
                 )
                 ELSE now() END
        FROM resolved_message_source AS source
        JOIN message_conversations AS conversation
          ON conversation.low_account_id = LEAST(
                 source.sender_account_id, source.receiver_account_id
             )
         AND conversation.high_account_id = GREATEST(
                 source.sender_account_id, source.receiver_account_id
             )
        ON CONFLICT (legacy_source_id)
        WHERE legacy_source_id IS NOT NULL
        DO NOTHING
        """
    ))
    op.execute(sa.text(
        "WITH " + MESSAGE_SOURCE_CTES + r"""
        UPDATE messages AS message
        SET reply_to_id = reply.id
        FROM resolved_message_source AS source
        JOIN messages AS reply
          ON reply.legacy_source_id = CASE
               WHEN COALESCE(source.row_data->>'reply_to_id', '') ~ '^[0-9]+$'
               THEN (source.row_data->>'reply_to_id')::bigint
               ELSE -1 END
        WHERE message.legacy_source_id = source.legacy_source_id
          AND message.conversation_id = reply.conversation_id
          AND message.reply_to_id IS NULL
        """
    ))


def downgrade() -> None:
    op.drop_index("uq_messages_legacy_source", table_name="messages")
    op.drop_index("ix_messages_receiver_unread", table_name="messages")
    op.drop_index("ix_messages_reply_to", table_name="messages")
    op.drop_index("ix_messages_receiver", table_name="messages")
    op.drop_index("ix_messages_sender", table_name="messages")
    op.drop_index("ix_message_conversation_member", table_name="messages")
    op.drop_table("messages")
    op.drop_index(
        "ix_message_members_account_conversation",
        table_name="message_conversation_members",
    )
    op.drop_table("message_conversation_members")
    op.drop_index(
        "ix_message_conversations_high_updated",
        table_name="message_conversations",
    )
    op.drop_index(
        "ix_message_conversations_low_updated",
        table_name="message_conversations",
    )
    op.drop_index(
        "uq_message_conversations_pair",
        table_name="message_conversations",
    )
    op.drop_table("message_conversations")
