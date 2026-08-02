"""V7 importidan keyin navbat xodimlari va xizmatlarini qayta to'ldirish.

Revision ID: 0013_queue_provider_backfill
Revises: 0012_queue_domain
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_queue_provider_backfill"
down_revision = "0012_queue_domain"
branch_labels = None
depends_on = None


# 0012 Alembic sxemasi haqiqiy V7 importidan oldin ishlagan muhitlarda
# queue_providers bo'sh qolgan. Relatsion cabinet_records asosiy manba,
# business_profiles.cabinet_payload esa dual-write fallback bo'lib qoladi.
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
        'medical_doctors', 'medical_doctor_services',
        'staff', 'business_staff', 'employees'
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


PROVIDER_BACKFILL_SQL = fr"""
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
    CASE WHEN COALESCE(source.row_data->>'work_start', '')
                   ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'
         THEN (source.row_data->>'work_start')::time ELSE '08:00'::time END,
    CASE WHEN COALESCE(source.row_data->>'work_end', '')
                   ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'
         THEN (source.row_data->>'work_end')::time ELSE '17:00'::time END,
    CASE WHEN COALESCE(source.row_data->>'avg_minutes', '') ~ '^[0-9]+$'
         THEN GREATEST(5, LEAST(240, (source.row_data->>'avg_minutes')::integer))
         ELSE 20 END,
    left(COALESCE(source.row_data->>'room', ''), 50),
    left(COALESCE(source.row_data->>'bio', ''), 500),
    CASE WHEN source.row_data->>'status' = 'inactive'
         THEN 'inactive' ELSE 'active' END,
    CASE WHEN source.row_data->>'mode' = 'slot' THEN 'slot' ELSE 'live' END,
    CASE WHEN COALESCE(source.row_data->>'created_at', '')
                   ~ '^[0-9]+([.][0-9]+)?$'
         THEN to_timestamp((source.row_data->>'created_at')::double precision)
         ELSE now() END,
    CASE WHEN COALESCE(source.row_data->>'updated_at', '')
                   ~ '^[0-9]+([.][0-9]+)?$'
         THEN to_timestamp((source.row_data->>'updated_at')::double precision)
         ELSE now() END
FROM provider_source AS source
ON CONFLICT (business_account_id, legacy_staff_id) DO NOTHING
"""


SERVICE_BACKFILL_SQL = fr"""
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
         THEN GREATEST(
             5,
             LEAST(240, (source.row_data->>'duration_minutes')::integer)
         )
         ELSE source.avg_minutes END,
    now(),
    now()
FROM mapped_links AS source
ON CONFLICT (provider_id, catalog_item_id) DO NOTHING
"""


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text(PROVIDER_BACKFILL_SQL))
    connection.execute(sa.text(SERVICE_BACKFILL_SQL))


def downgrade() -> None:
    # Qaysi provider 0012, 0013 yoki typed API orqali yaratilganini ajratuvchi
    # marker yo'q. Jonli navbat ma'lumotini o'chirmaslik uchun data repair qaytmaydi.
    pass
