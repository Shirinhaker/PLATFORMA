"""Navbat tizimini alohida relatsion domenga ko'chirish.

Revision ID: 0012_queue_domain
Revises: 0011_notifications_relational
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_queue_domain"
down_revision = "0011_notifications_relational"
branch_labels = None
depends_on = None


# Relatsion cabinet_records birinchi manba, business_profiles.cabinet_payload esa
# hali dual-write davrida qolgan yozuvlar uchun fallback. Root scalar maydonlar
# qayta yig'iladi; provider-service bog'lanishi alohida resource orqali olinadi.
QUEUE_SOURCE_CTES = r"""
relational_queue_rows AS (
    SELECT
        resource.account_id,
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
    WHERE resource.account_type = 'business'
      AND resource.resource IN (
        'medical_doctors', 'medical_doctor_services', 'medical_queue',
        'medical_queue_history', 'staff', 'business_staff', 'employees'
      )
    GROUP BY
        resource.account_id,
        resource.resource,
        record.id,
        record.source_key,
        record.ordinal
),
payload_queue_rows AS (
    SELECT
        profile.account_id,
        resource_name.resource,
        COALESCE(
            NULLIF(entry.row_data->>'id', ''),
            'ordinal:' || entry.ordinality
        ) AS source_key,
        entry.ordinality::integer AS ordinal,
        entry.row_data,
        1 AS priority
    FROM business_profiles AS profile
    CROSS JOIN LATERAL (
        VALUES
            ('medical_doctors'),
            ('medical_doctor_services'),
            ('medical_queue'),
            ('medical_queue_history'),
            ('staff'),
            ('business_staff'),
            ('employees')
    ) AS resource_name(resource)
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(
                COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)
                -> resource_name.resource
            ) = 'array'
            THEN COALESCE(profile.cabinet_payload::jsonb, '{}'::jsonb)
                -> resource_name.resource
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
),
all_queue_rows AS (
    SELECT * FROM relational_queue_rows
    UNION ALL
    SELECT * FROM payload_queue_rows
),
queue_source AS (
    SELECT DISTINCT ON (account_id, resource, source_key)
        account_id,
        resource,
        source_key,
        ordinal,
        row_data
    FROM all_queue_rows
    ORDER BY account_id, resource, source_key, priority, ordinal
)
"""


SUPPORTED_DIRECTIONS_SQL = r"""
(
    'Transport va logistika',
    'Xizmat ko''rsatish',
    'Maishiy xizmatlar',
    'Qurilish',
    'Tibbiy xizmatlar',
    'Ko''chmas mulk',
    'Axborot texnologiyalari',
    'Konsalting va professional',
    'Madaniyat, sport, ko''ngilochar',
    'Turizm va mehmonxona',
    'Reklama va marketing',
    'Poligrafiya va nashriyot',
    'Moliyaviy faoliyat',
    'Import-eksport'
)
"""


def upgrade() -> None:
    op.create_table(
        "queue_providers",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("legacy_staff_id", sa.BigInteger(), nullable=False),
        sa.Column("staff_name_snapshot", sa.String(length=120), nullable=False),
        sa.Column("profession_snapshot", sa.String(length=120), nullable=False),
        sa.Column("specialty", sa.String(length=100), nullable=False),
        sa.Column("experience_years", sa.Integer(), nullable=False),
        sa.Column("qualification", sa.String(length=100), nullable=False),
        sa.Column("work_days", sa.String(length=30), nullable=False),
        sa.Column("work_start", sa.Time(), nullable=False),
        sa.Column("work_end", sa.Time(), nullable=False),
        sa.Column("avg_minutes", sa.Integer(), nullable=False),
        sa.Column("room", sa.String(length=50), nullable=False),
        sa.Column("bio", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "experience_years >= 0",
            name="ck_queue_providers_experience_years",
        ),
        sa.CheckConstraint(
            "avg_minutes BETWEEN 5 AND 240",
            name="ck_queue_providers_avg_minutes",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_queue_providers_status",
        ),
        sa.CheckConstraint(
            "mode IN ('live', 'slot')",
            name="ck_queue_providers_mode",
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "uq_queue_providers_business_staff",
        "queue_providers",
        ["business_account_id", "legacy_staff_id"],
        unique=True,
    )
    op.create_index(
        "uq_queue_providers_business_legacy",
        "queue_providers",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "ix_queue_providers_business_status",
        "queue_providers",
        ["business_account_id", "status", "staff_name_snapshot"],
    )

    op.create_table(
        "queue_provider_services",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("provider_id", sa.BigInteger(), nullable=False),
        sa.Column("catalog_item_id", sa.BigInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "duration_minutes BETWEEN 5 AND 240",
            name="ck_queue_provider_services_duration",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["queue_providers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["catalog_item_id"], ["catalog_items.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "uq_queue_provider_services_provider_item",
        "queue_provider_services",
        ["provider_id", "catalog_item_id"],
        unique=True,
    )
    op.create_index(
        "ix_queue_provider_services_item_active",
        "queue_provider_services",
        ["catalog_item_id", "active", "provider_id"],
    )

    op.create_table(
        "queue_entries",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("catalog_item_id", sa.BigInteger()),
        sa.Column("provider_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_account_id", sa.BigInteger()),
        sa.Column("patient_name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("service_name_snapshot", sa.String(length=160), nullable=False),
        sa.Column("provider_name_snapshot", sa.String(length=120), nullable=False),
        sa.Column("queue_date", sa.Date(), nullable=False),
        sa.Column("queue_no", sa.Integer(), nullable=False),
        sa.Column("queue_code", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=12), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=False),
        sa.Column("slot_time", sa.Time()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source IN ('online', 'offline')",
            name="ck_queue_entries_source",
        ),
        sa.CheckConstraint(
            "status IN ('waiting', 'called', 'in_service', 'done', "
            "'no_show', 'cancelled', 'skipped')",
            name="ck_queue_entries_status",
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["catalog_item_id"], ["catalog_items.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["queue_providers.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["customer_account_id"], ["accounts.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "uq_queue_entries_business_legacy",
        "queue_entries",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "uq_queue_entries_number",
        "queue_entries",
        [
            "business_account_id",
            "catalog_item_id",
            "provider_id",
            "queue_date",
            "queue_no",
        ],
        unique=True,
    )
    op.create_index(
        "uq_queue_entries_slot",
        "queue_entries",
        [
            "business_account_id",
            "catalog_item_id",
            "provider_id",
            "queue_date",
            "slot_time",
        ],
        unique=True,
        postgresql_where=sa.text("slot_time IS NOT NULL"),
    )
    op.create_index(
        "uq_queue_entries_active_customer_live",
        "queue_entries",
        [
            "business_account_id",
            "catalog_item_id",
            "provider_id",
            "queue_date",
            "customer_account_id",
        ],
        unique=True,
        postgresql_where=sa.text(
            "customer_account_id IS NOT NULL AND slot_time IS NULL AND "
            "status IN ('waiting', 'called', 'in_service')"
        ),
    )
    op.create_index(
        "ix_queue_entries_business_day",
        "queue_entries",
        [
            "business_account_id",
            "queue_date",
            "provider_id",
            "catalog_item_id",
            "queue_no",
        ],
    )
    op.create_index(
        "ix_queue_entries_ahead",
        "queue_entries",
        ["provider_id", "catalog_item_id", "queue_date", "status", "queue_no"],
    )
    op.create_index(
        "ix_queue_entries_customer_created",
        "queue_entries",
        ["customer_account_id", "queue_date", "created_at", "id"],
    )
    op.create_index(
        "ix_queue_entries_catalog_item_id",
        "queue_entries",
        ["catalog_item_id"],
    )

    op.create_table(
        "queue_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("queue_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("old_value", sa.String(length=160), nullable=False),
        sa.Column("new_value", sa.String(length=160), nullable=False),
        sa.Column("actor_account_id", sa.BigInteger()),
        sa.Column("legacy_actor_staff_id", sa.BigInteger()),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["queue_id"], ["queue_entries.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["actor_account_id"], ["accounts.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_queue_history_queue",
        "queue_history",
        ["queue_id", "id"],
    )
    op.create_index(
        "ix_queue_history_business_account_id",
        "queue_history",
        ["business_account_id"],
    )
    op.create_index(
        "ix_queue_history_actor_account_id",
        "queue_history",
        ["actor_account_id"],
    )
    op.create_index(
        "uq_queue_history_business_legacy",
        "queue_history",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )

    op.create_table(
        "queue_counters",
        sa.Column("business_account_id", sa.BigInteger(), primary_key=True),
        sa.Column("catalog_item_id", sa.BigInteger(), primary_key=True),
        sa.Column("provider_id", sa.BigInteger(), primary_key=True),
        sa.Column("queue_date", sa.Date(), primary_key=True),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "last_number >= 0",
            name="ck_queue_counters_last_number",
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["catalog_item_id"], ["catalog_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["queue_providers.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_queue_counters_catalog_item_id",
        "queue_counters",
        ["catalog_item_id"],
    )
    op.create_index(
        "ix_queue_counters_provider_id",
        "queue_counters",
        ["provider_id"],
    )

    connection = op.get_bind()

    # Provider: Tizimlashtirish xodim yozuvlari o'zgartirilmaydi. Ularning ID,
    # ism va kasbi faqat queue_providers ichiga snapshot sifatida o'qiladi.
    connection.execute(sa.text(fr"""
        WITH {QUEUE_SOURCE_CTES}, provider_source AS (
            SELECT doctor.account_id,
                   doctor.source_key,
                   doctor.row_data,
                   staff.row_data AS staff_data
            FROM queue_source AS doctor
            JOIN business_profiles AS profile
              ON profile.account_id = doctor.account_id
             AND profile.direction IN {SUPPORTED_DIRECTIONS_SQL}
            LEFT JOIN LATERAL (
                SELECT candidate.row_data
                FROM queue_source AS candidate
                WHERE candidate.account_id = doctor.account_id
                  AND candidate.resource IN ('staff', 'business_staff', 'employees')
                  AND COALESCE(candidate.row_data->>'id', candidate.source_key) =
                      doctor.row_data->>'staff_id'
                ORDER BY CASE candidate.resource WHEN 'staff' THEN 0 ELSE 1 END
                LIMIT 1
            ) AS staff ON true
            WHERE doctor.resource = 'medical_doctors'
              AND COALESCE(doctor.row_data->>'staff_id', '') ~ '^[0-9]+$'
        )
        INSERT INTO queue_providers (
            business_account_id,
            legacy_source_id,
            legacy_staff_id,
            staff_name_snapshot,
            profession_snapshot,
            specialty,
            experience_years,
            qualification,
            work_days,
            work_start,
            work_end,
            avg_minutes,
            room,
            bio,
            status,
            mode,
            created_at,
            updated_at
        )
        SELECT
            source.account_id,
            CASE
                WHEN COALESCE(source.row_data->>'id', source.source_key) ~ '^[0-9]+$'
                THEN COALESCE(source.row_data->>'id', source.source_key)::bigint
                ELSE NULL
            END,
            (source.row_data->>'staff_id')::bigint,
            left(COALESCE(
                NULLIF(source.row_data->>'name', ''),
                NULLIF(source.staff_data->>'name', ''),
                ''
            ), 120),
            left(COALESCE(
                NULLIF(source.row_data->>'profession', ''),
                NULLIF(source.staff_data->>'profession', ''),
                'Xodim'
            ), 120),
            left(COALESCE(source.row_data->>'specialty', ''), 100),
            CASE WHEN COALESCE(source.row_data->>'experience_years', '') ~ '^[0-9]+$'
                 THEN (source.row_data->>'experience_years')::integer ELSE 0 END,
            left(COALESCE(source.row_data->>'qualification', ''), 100),
            left(COALESCE(NULLIF(source.row_data->>'work_days', ''), '1,2,3,4,5,6'), 30),
            CASE WHEN COALESCE(source.row_data->>'work_start', '') ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'
                 THEN (source.row_data->>'work_start')::time ELSE '08:00'::time END,
            CASE WHEN COALESCE(source.row_data->>'work_end', '') ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'
                 THEN (source.row_data->>'work_end')::time ELSE '17:00'::time END,
            CASE WHEN COALESCE(source.row_data->>'avg_minutes', '') ~ '^[0-9]+$'
                 THEN GREATEST(5, LEAST(240, (source.row_data->>'avg_minutes')::integer))
                 ELSE 20 END,
            left(COALESCE(source.row_data->>'room', ''), 50),
            left(COALESCE(source.row_data->>'bio', ''), 500),
            CASE WHEN source.row_data->>'status' = 'inactive' THEN 'inactive' ELSE 'active' END,
            CASE WHEN source.row_data->>'mode' = 'slot' THEN 'slot' ELSE 'live' END,
            CASE WHEN COALESCE(source.row_data->>'created_at', '') ~ '^[0-9]+([.][0-9]+)?$'
                 THEN to_timestamp((source.row_data->>'created_at')::double precision) ELSE now() END,
            CASE WHEN COALESCE(source.row_data->>'updated_at', '') ~ '^[0-9]+([.][0-9]+)?$'
                 THEN to_timestamp((source.row_data->>'updated_at')::double precision) ELSE now() END
        FROM provider_source AS source
        ON CONFLICT (business_account_id, legacy_staff_id) DO UPDATE SET
            legacy_source_id = COALESCE(
                queue_providers.legacy_source_id,
                EXCLUDED.legacy_source_id
            ),
            staff_name_snapshot = EXCLUDED.staff_name_snapshot,
            profession_snapshot = EXCLUDED.profession_snapshot,
            specialty = EXCLUDED.specialty,
            experience_years = EXCLUDED.experience_years,
            qualification = EXCLUDED.qualification,
            work_days = EXCLUDED.work_days,
            work_start = EXCLUDED.work_start,
            work_end = EXCLUDED.work_end,
            avg_minutes = EXCLUDED.avg_minutes,
            room = EXCLUDED.room,
            bio = EXCLUDED.bio,
            status = EXCLUDED.status,
            mode = EXCLUDED.mode,
            updated_at = EXCLUDED.updated_at
    """))

    connection.execute(sa.text(fr"""
        WITH {QUEUE_SOURCE_CTES}, mapped_links AS (
            SELECT provider.id AS provider_id,
                   item.id AS catalog_item_id,
                   provider.avg_minutes,
                   link.row_data
            FROM queue_source AS link
            JOIN queue_providers AS provider
              ON provider.business_account_id = link.account_id
             AND provider.legacy_staff_id = CASE
                    WHEN COALESCE(link.row_data->>'staff_id', '') ~ '^[0-9]+$'
                    THEN (link.row_data->>'staff_id')::bigint ELSE NULL END
            JOIN catalog_items AS item
              ON item.business_account_id = link.account_id
             AND item.source_record_key = link.row_data->>'item_id'
             AND item.kind = 'service'
            WHERE link.resource = 'medical_doctor_services'
              AND lower(COALESCE(link.row_data->>'active', '1'))
                  IN ('1', 'true', 'yes', 'on')
        )
        INSERT INTO queue_provider_services (
            provider_id,
            catalog_item_id,
            active,
            duration_minutes,
            created_at,
            updated_at
        )
        SELECT
            source.provider_id,
            source.catalog_item_id,
            true,
            CASE WHEN COALESCE(source.row_data->>'duration_minutes', '') ~ '^[0-9]+$'
                 THEN GREATEST(5, LEAST(240, (source.row_data->>'duration_minutes')::integer))
                 ELSE source.avg_minutes END,
            now(),
            now()
        FROM mapped_links AS source
        ON CONFLICT (provider_id, catalog_item_id) DO UPDATE SET
            active = EXCLUDED.active,
            duration_minutes = EXCLUDED.duration_minutes,
            updated_at = EXCLUDED.updated_at
    """))

    connection.execute(sa.text(fr"""
        WITH {QUEUE_SOURCE_CTES}, mapped_queue AS (
            SELECT queue.account_id,
                   queue.source_key,
                   queue.row_data,
                   provider.id AS provider_id,
                   provider.staff_name_snapshot,
                   item.id AS catalog_item_id,
                   item.name AS service_name,
                   COALESCE(user_map.target_id, direct_user.id) AS customer_account_id
            FROM queue_source AS queue
            JOIN queue_providers AS provider
              ON provider.business_account_id = queue.account_id
             AND provider.legacy_staff_id = CASE
                    WHEN COALESCE(queue.row_data->>'staff_id', '') ~ '^[0-9]+$'
                    THEN (queue.row_data->>'staff_id')::bigint ELSE NULL END
            JOIN catalog_items AS item
              ON item.business_account_id = queue.account_id
             AND item.source_record_key = queue.row_data->>'item_id'
             AND item.kind = 'service'
            LEFT JOIN legacy_id_map AS user_map
              ON user_map.entity_type = 'user_account'
             AND user_map.legacy_id = CASE
                    WHEN COALESCE(queue.row_data->>'user_id', '') ~ '^[0-9]+$'
                    THEN (queue.row_data->>'user_id')::bigint ELSE NULL END
            LEFT JOIN accounts AS direct_user
              ON direct_user.id = CASE
                    WHEN COALESCE(queue.row_data->>'user_id', '') ~ '^[0-9]+$'
                    THEN (queue.row_data->>'user_id')::bigint ELSE NULL END
             AND direct_user.account_type::text = 'user'
            WHERE queue.resource = 'medical_queue'
              AND COALESCE(queue.row_data->>'queue_date', '') ~ '^\d{4}-\d{2}-\d{2}$'
              AND COALESCE(queue.row_data->>'queue_no', '') ~ '^-?[0-9]+$'
        )
        INSERT INTO queue_entries (
            business_account_id,
            legacy_source_id,
            catalog_item_id,
            provider_id,
            customer_account_id,
            patient_name,
            phone,
            service_name_snapshot,
            provider_name_snapshot,
            queue_date,
            queue_no,
            queue_code,
            source,
            status,
            note,
            slot_time,
            created_at,
            updated_at
        )
        SELECT
            source.account_id,
            CASE WHEN COALESCE(source.row_data->>'id', source.source_key) ~ '^[0-9]+$'
                 THEN COALESCE(source.row_data->>'id', source.source_key)::bigint ELSE NULL END,
            source.catalog_item_id,
            source.provider_id,
            source.customer_account_id,
            left(COALESCE(NULLIF(source.row_data->>'patient_name', ''), 'Bemor'), 120),
            left(COALESCE(source.row_data->>'phone', ''), 32),
            left(source.service_name, 160),
            left(source.staff_name_snapshot, 120),
            (source.row_data->>'queue_date')::date,
            (source.row_data->>'queue_no')::integer,
            left(COALESCE(NULLIF(source.row_data->>'queue_code', ''), 'NAV-001'), 32),
            CASE WHEN source.row_data->>'source' = 'offline' THEN 'offline' ELSE 'online' END,
            CASE WHEN source.row_data->>'status' IN (
                    'waiting', 'called', 'in_service', 'done',
                    'no_show', 'cancelled', 'skipped'
                 ) THEN source.row_data->>'status' ELSE 'waiting' END,
            left(COALESCE(source.row_data->>'note', ''), 200),
            CASE WHEN COALESCE(source.row_data->>'slot_time', '')
                           ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'
                 THEN (source.row_data->>'slot_time')::time ELSE NULL END,
            CASE WHEN COALESCE(source.row_data->>'created_at', '') ~ '^[0-9]+([.][0-9]+)?$'
                 THEN to_timestamp((source.row_data->>'created_at')::double precision) ELSE now() END,
            CASE WHEN COALESCE(source.row_data->>'updated_at', '') ~ '^[0-9]+([.][0-9]+)?$'
                 THEN to_timestamp((source.row_data->>'updated_at')::double precision) ELSE now() END
        FROM mapped_queue AS source
        WHERE COALESCE(source.row_data->>'id', source.source_key) ~ '^[0-9]+$'
        ON CONFLICT (business_account_id, legacy_source_id)
            WHERE legacy_source_id IS NOT NULL
        DO UPDATE SET
            customer_account_id = EXCLUDED.customer_account_id,
            patient_name = EXCLUDED.patient_name,
            phone = EXCLUDED.phone,
            queue_no = EXCLUDED.queue_no,
            queue_code = EXCLUDED.queue_code,
            status = EXCLUDED.status,
            note = EXCLUDED.note,
            slot_time = EXCLUDED.slot_time,
            updated_at = EXCLUDED.updated_at
    """))

    connection.execute(sa.text(fr"""
        WITH {QUEUE_SOURCE_CTES}, mapped_history AS (
            SELECT history.account_id,
                   history.source_key,
                   history.row_data,
                   entry.id AS queue_id,
                   COALESCE(actor_map.target_id, direct_actor.id) AS actor_account_id
            FROM queue_source AS history
            JOIN queue_entries AS entry
              ON entry.business_account_id = history.account_id
             AND entry.legacy_source_id = CASE
                    WHEN COALESCE(history.row_data->>'queue_id', '') ~ '^[0-9]+$'
                    THEN (history.row_data->>'queue_id')::bigint ELSE NULL END
            LEFT JOIN legacy_id_map AS actor_map
              ON actor_map.entity_type = 'user_account'
             AND actor_map.legacy_id = CASE
                    WHEN COALESCE(history.row_data->>'actor_user_id', '') ~ '^[0-9]+$'
                    THEN (history.row_data->>'actor_user_id')::bigint ELSE NULL END
            LEFT JOIN accounts AS direct_actor
              ON direct_actor.id = CASE
                    WHEN COALESCE(history.row_data->>'actor_user_id', '') ~ '^[0-9]+$'
                    THEN (history.row_data->>'actor_user_id')::bigint ELSE NULL END
            WHERE history.resource = 'medical_queue_history'
        )
        INSERT INTO queue_history (
            business_account_id,
            queue_id,
            legacy_source_id,
            action,
            old_value,
            new_value,
            actor_account_id,
            legacy_actor_staff_id,
            note,
            created_at
        )
        SELECT
            source.account_id,
            source.queue_id,
            CASE WHEN COALESCE(source.row_data->>'id', source.source_key) ~ '^[0-9]+$'
                 THEN COALESCE(source.row_data->>'id', source.source_key)::bigint ELSE NULL END,
            left(COALESCE(NULLIF(source.row_data->>'action', ''), 'status'), 40),
            left(COALESCE(source.row_data->>'old_value', ''), 160),
            left(COALESCE(source.row_data->>'new_value', ''), 160),
            source.actor_account_id,
            CASE WHEN COALESCE(source.row_data->>'actor_staff_id', '') ~ '^[0-9]+$'
                 THEN (source.row_data->>'actor_staff_id')::bigint ELSE NULL END,
            COALESCE(source.row_data->>'note', ''),
            CASE WHEN COALESCE(source.row_data->>'created_at', '') ~ '^[0-9]+([.][0-9]+)?$'
                 THEN to_timestamp((source.row_data->>'created_at')::double precision) ELSE now() END
        FROM mapped_history AS source
        WHERE COALESCE(source.row_data->>'id', source.source_key) ~ '^[0-9]+$'
        ON CONFLICT (business_account_id, legacy_source_id)
            WHERE legacy_source_id IS NOT NULL
        DO NOTHING
    """))

    # Har live navbat kesimi uchun oxirgi raqamni bir marta hisoblaymiz. Keyingi
    # yozuvlar repositorydagi atomar UPSERT ... RETURNING orqali ajratiladi.
    connection.execute(sa.text(r"""
        INSERT INTO queue_counters (
            business_account_id,
            catalog_item_id,
            provider_id,
            queue_date,
            last_number,
            updated_at
        )
        SELECT
            business_account_id,
            catalog_item_id,
            provider_id,
            queue_date,
            MAX(queue_no),
            now()
        FROM queue_entries
        WHERE slot_time IS NULL
          AND catalog_item_id IS NOT NULL
          AND queue_no > 0
        GROUP BY business_account_id, catalog_item_id, provider_id, queue_date
        ON CONFLICT (
            business_account_id,
            catalog_item_id,
            provider_id,
            queue_date
        ) DO UPDATE SET
            last_number = GREATEST(
                queue_counters.last_number,
                EXCLUDED.last_number
            ),
            updated_at = EXCLUDED.updated_at
    """))


def downgrade() -> None:
    op.drop_table("queue_history")
    op.drop_table("queue_entries")
    op.drop_table("queue_provider_services")
    op.drop_table("queue_counters")
    op.drop_table("queue_providers")
