"""Xodimlar, vakolatlar, grafik, tabel va xodim sessiyalarini ko'chirish.

Revision ID: 0014_staff_domain
Revises: 0013_queue_provider_backfill
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_staff_domain"
down_revision = "0013_queue_provider_backfill"
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


STAFF_SOURCE_CTES = rf"""
WITH
relational_schedule_days AS (
    SELECT
        record.id AS record_id,
        split_part(field.path, '/', 3) AS day_key,
        jsonb_object_agg(
            split_part(field.path, '/', 4),
            {JSON_VALUE_SQL}
        ) AS day_value
    FROM cabinet_records AS record
    JOIN cabinet_record_fields AS field ON field.record_id = record.id
    WHERE field.path ~ '^/schedule/d[0-6]/(on|start|end|s|e)$'
    GROUP BY record.id, split_part(field.path, '/', 3)
),
relational_schedules AS (
    SELECT record_id, jsonb_object_agg(day_key, day_value) AS schedule
    FROM relational_schedule_days
    GROUP BY record_id
),
relational_staff_rows AS (
    SELECT
        resource.account_id,
        resource.resource,
        record.source_key,
        record.ordinal,
        COALESCE(
            jsonb_object_agg(
                substr(field.path, 2),
                {JSON_VALUE_SQL}
            ) FILTER (WHERE field.path ~ '^/[^/]+$'),
            '{{}}'::jsonb
        ) || jsonb_build_object(
            'schedule', COALESCE(schedule.schedule, '{{}}'::jsonb)
        ) AS row_data,
        0 AS priority
    FROM cabinet_resources AS resource
    JOIN cabinet_records AS record ON record.resource_id = resource.id
    LEFT JOIN cabinet_record_fields AS field ON field.record_id = record.id
    LEFT JOIN relational_schedules AS schedule ON schedule.record_id = record.id
    WHERE resource.account_type = 'business'
      AND resource.resource IN ('staff', 'business_staff', 'employees')
    GROUP BY
        resource.account_id, resource.resource, record.id,
        record.source_key, record.ordinal, schedule.schedule
),
payload_staff_rows AS (
    SELECT
        profile.account_id,
        resource_name.resource,
        COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality)
            AS source_key,
        entry.ordinality::integer AS ordinal,
        entry.row_data,
        1 AS priority
    FROM business_profiles AS profile
    CROSS JOIN LATERAL (
        VALUES ('staff'), ('business_staff'), ('employees')
    ) AS resource_name(resource)
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(
                COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
                -> resource_name.resource
            ) = 'array'
            THEN COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
                -> resource_name.resource
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
),
all_staff_rows AS (
    SELECT * FROM relational_staff_rows
    UNION ALL
    SELECT * FROM payload_staff_rows
),
staff_source AS (
    SELECT DISTINCT ON (account_id, legacy_source_id)
        account_id,
        legacy_source_id,
        row_data
    FROM (
        SELECT
            account_id,
            CASE
                WHEN COALESCE(row_data->>'id', source_key, '') ~ '^[0-9]+$'
                THEN COALESCE(row_data->>'id', source_key)::bigint
                ELSE NULL
            END AS legacy_source_id,
            row_data,
            priority,
            CASE resource WHEN 'staff' THEN 0 WHEN 'business_staff' THEN 1 ELSE 2 END
                AS resource_priority,
            ordinal
        FROM all_staff_rows
    ) AS ranked
    WHERE legacy_source_id IS NOT NULL
      AND COALESCE(NULLIF(trim(row_data->>'name'), ''), '') <> ''
    ORDER BY account_id, legacy_source_id, priority, resource_priority, ordinal
)
"""


STAFF_BACKFILL_SQL = STAFF_SOURCE_CTES + r"""
INSERT INTO staff_members (
    business_account_id, legacy_source_id, name, profession, phone, salary,
    hire_date, status, note, login, password_hash, can_login, permissions,
    schedule, created_at, updated_at, fired_at
)
SELECT
    source.account_id,
    source.legacy_source_id,
    left(trim(source.row_data->>'name'), 120),
    left(COALESCE(source.row_data->>'profession', ''), 80),
    left(COALESCE(source.row_data->>'phone', ''), 32),
    CASE WHEN COALESCE(source.row_data->>'salary', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'salary')::bigint ELSE 0 END,
    CASE WHEN COALESCE(source.row_data->>'hire_date', '') ~ '^\d{4}-\d{2}-\d{2}$'
        THEN to_date(source.row_data->>'hire_date', 'YYYY-MM-DD') ELSE NULL END,
    CASE WHEN source.row_data->>'status' = 'fired' THEN 'fired' ELSE 'active' END,
    left(COALESCE(source.row_data->>'note', ''), 500),
    CASE WHEN lower(COALESCE(source.row_data->>'login', '')) ~ '^[a-z][a-z0-9_]{2,19}$'
        THEN lower(source.row_data->>'login') ELSE NULL END,
    NULL::varchar,
    false,
    CASE WHEN jsonb_typeof(source.row_data->'perms') = 'array'
        THEN source.row_data->'perms'
        WHEN jsonb_typeof(source.row_data->'permissions') = 'array'
        THEN source.row_data->'permissions'
        ELSE '[]'::jsonb END,
    CASE WHEN jsonb_typeof(source.row_data->'schedule') = 'object'
        THEN source.row_data->'schedule' ELSE '{}'::jsonb END,
    CASE WHEN COALESCE(source.row_data->>'created_at', '') ~ '^[0-9]+$'
        THEN to_timestamp((source.row_data->>'created_at')::double precision)
        ELSE now() END,
    now(),
    CASE
        WHEN source.row_data->>'status' = 'fired'
         AND COALESCE(source.row_data->>'fired_at', '') ~ '^[0-9]+$'
        THEN to_timestamp((source.row_data->>'fired_at')::double precision)
        ELSE NULL
    END
FROM staff_source AS source
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO UPDATE SET
    name = EXCLUDED.name,
    profession = EXCLUDED.profession,
    phone = EXCLUDED.phone,
    salary = EXCLUDED.salary,
    hire_date = EXCLUDED.hire_date,
    status = EXCLUDED.status,
    note = EXCLUDED.note,
    schedule = EXCLUDED.schedule,
    updated_at = now(),
    fired_at = EXCLUDED.fired_at
"""


GENERIC_SOURCE_CTES = rf"""
WITH
relational_generic_rows AS (
    SELECT
        resource.account_id,
        resource.resource,
        record.source_key,
        record.ordinal,
        COALESCE(
            jsonb_object_agg(
                substr(field.path, 2),
                {JSON_VALUE_SQL}
            ) FILTER (WHERE field.path ~ '^/[^/]+$'),
            '{{}}'::jsonb
        ) AS row_data,
        0 AS priority
    FROM cabinet_resources AS resource
    JOIN cabinet_records AS record ON record.resource_id = resource.id
    LEFT JOIN cabinet_record_fields AS field ON field.record_id = record.id
    WHERE resource.account_type = 'business'
      AND resource.resource IN ('staff_professions', 'staff_attendance')
    GROUP BY resource.account_id, resource.resource, record.id,
             record.source_key, record.ordinal
),
payload_generic_rows AS (
    SELECT
        profile.account_id,
        resource_name.resource,
        COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality)
            AS source_key,
        entry.ordinality::integer AS ordinal,
        entry.row_data,
        1 AS priority
    FROM business_profiles AS profile
    CROSS JOIN LATERAL (
        VALUES ('staff_professions'), ('staff_attendance')
    ) AS resource_name(resource)
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(
                COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
                -> resource_name.resource
            ) = 'array'
            THEN COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
                -> resource_name.resource
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
),
generic_source AS (
    SELECT DISTINCT ON (account_id, resource, source_key)
        account_id, resource, source_key, row_data
    FROM (
        SELECT * FROM relational_generic_rows
        UNION ALL
        SELECT * FROM payload_generic_rows
    ) AS source
    ORDER BY account_id, resource, source_key, priority, ordinal
)
"""


PROFESSION_BACKFILL_SQL = GENERIC_SOURCE_CTES + r"""
INSERT INTO staff_professions (business_account_id, name, created_at)
SELECT
    source.account_id,
    left(trim(source.row_data->>'name'), 80),
    now()
FROM generic_source AS source
WHERE source.resource = 'staff_professions'
  AND COALESCE(NULLIF(trim(source.row_data->>'name'), ''), '') <> ''
ON CONFLICT (business_account_id, lower(name)) DO NOTHING
"""


ATTENDANCE_BACKFILL_SQL = GENERIC_SOURCE_CTES + r"""
INSERT INTO staff_attendance (
    business_account_id, staff_id, date, status, time_in, time_out,
    created_at, updated_at
)
SELECT
    source.account_id,
    member.id,
    to_date(source.row_data->>'date', 'YYYY-MM-DD'),
    source.row_data->>'status',
    CASE WHEN COALESCE(source.row_data->>'time_in', '') ~ '^([01]\d|2[0-3]):[0-5]\d$'
        THEN (source.row_data->>'time_in')::time ELSE NULL END,
    CASE WHEN COALESCE(source.row_data->>'time_out', '') ~ '^([01]\d|2[0-3]):[0-5]\d$'
        THEN (source.row_data->>'time_out')::time ELSE NULL END,
    now(),
    now()
FROM generic_source AS source
JOIN staff_members AS member
  ON member.business_account_id = source.account_id
 AND member.legacy_source_id = CASE
        WHEN COALESCE(source.row_data->>'staff_id', '') ~ '^[0-9]+$'
        THEN (source.row_data->>'staff_id')::bigint ELSE NULL END
WHERE source.resource = 'staff_attendance'
  AND COALESCE(source.row_data->>'date', '') ~ '^\d{4}-\d{2}-\d{2}$'
  AND source.row_data->>'status' IN ('keldi', 'kelmadi', 'dam')
ON CONFLICT (staff_id, date) DO UPDATE SET
    status = EXCLUDED.status,
    time_in = EXCLUDED.time_in,
    time_out = EXCLUDED.time_out,
    updated_at = now()
"""


QUEUE_STAFF_REMAP_STAGE_SQL = r"""
UPDATE queue_providers AS provider
SET legacy_staff_id = -member.id
FROM staff_members AS member
WHERE member.business_account_id = provider.business_account_id
  AND member.legacy_source_id = provider.legacy_staff_id
  AND provider.legacy_staff_id <> member.id
  AND provider.legacy_staff_id > 0
"""


QUEUE_STAFF_REMAP_SQL = r"""
UPDATE queue_providers AS provider
SET legacy_staff_id = member.id
FROM staff_members AS member
WHERE member.business_account_id = provider.business_account_id
  AND provider.legacy_staff_id = -member.id
"""


QUEUE_STAFF_RESTORE_STAGE_SQL = r"""
UPDATE queue_providers AS provider
SET legacy_staff_id = -member.legacy_source_id
FROM staff_members AS member
WHERE member.business_account_id = provider.business_account_id
  AND provider.legacy_staff_id = member.id
  AND member.legacy_source_id IS NOT NULL
  AND member.legacy_source_id <> member.id
"""


QUEUE_STAFF_RESTORE_SQL = r"""
UPDATE queue_providers AS provider
SET legacy_staff_id = member.legacy_source_id
FROM staff_members AS member
WHERE member.business_account_id = provider.business_account_id
  AND provider.legacy_staff_id = -member.legacy_source_id
  AND member.legacy_source_id IS NOT NULL
"""


def upgrade() -> None:
    op.create_table(
        "staff_members",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("profession", sa.String(length=80), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("salary", sa.BigInteger(), nullable=False),
        sa.Column("hire_date", sa.Date()),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=False),
        sa.Column("login", sa.String(length=20)),
        sa.Column("password_hash", sa.String(length=255)),
        sa.Column("can_login", sa.Boolean(), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("schedule", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("salary >= 0", name="ck_staff_members_salary"),
        sa.CheckConstraint(
            "status IN ('active', 'fired')", name="ck_staff_members_status"
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "uq_staff_members_business_legacy",
        "staff_members",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "uq_staff_members_business_login",
        "staff_members",
        ["business_account_id", sa.text("lower(login)")],
        unique=True,
        postgresql_where=sa.text("login IS NOT NULL AND login <> ''"),
    )
    op.create_index(
        "ix_staff_members_business_status_name",
        "staff_members",
        ["business_account_id", "status", "name"],
    )

    op.create_table(
        "staff_professions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "uq_staff_professions_business_name",
        "staff_professions",
        ["business_account_id", sa.text("lower(name)")],
        unique=True,
    )

    op.create_table(
        "staff_attendance",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("staff_id", sa.BigInteger(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("time_in", sa.Time()),
        sa.Column("time_out", sa.Time()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('keldi', 'kelmadi', 'dam')",
            name="ck_staff_attendance_status",
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["staff_id"], ["staff_members.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "uq_staff_attendance_staff_date",
        "staff_attendance",
        ["staff_id", "date"],
        unique=True,
    )
    op.create_index(
        "ix_staff_attendance_business_date",
        "staff_attendance",
        ["business_account_id", "date", "staff_id"],
    )

    op.create_table(
        "staff_sessions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("staff_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["staff_id"], ["staff_members.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "uq_staff_sessions_token_hash",
        "staff_sessions",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_staff_sessions_active_staff",
        "staff_sessions",
        ["staff_id", "expires_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.execute(STAFF_BACKFILL_SQL)
    op.execute(PROFESSION_BACKFILL_SQL)
    op.execute(ATTENDANCE_BACKFILL_SQL)
    op.execute(QUEUE_STAFF_REMAP_STAGE_SQL)
    op.execute(QUEUE_STAFF_REMAP_SQL)


def downgrade() -> None:
    op.execute(QUEUE_STAFF_RESTORE_STAGE_SQL)
    op.execute(QUEUE_STAFF_RESTORE_SQL)
    op.drop_index("ix_staff_sessions_active_staff", table_name="staff_sessions")
    op.drop_index("uq_staff_sessions_token_hash", table_name="staff_sessions")
    op.drop_table("staff_sessions")
    op.drop_index("ix_staff_attendance_business_date", table_name="staff_attendance")
    op.drop_index("uq_staff_attendance_staff_date", table_name="staff_attendance")
    op.drop_table("staff_attendance")
    op.drop_index(
        "uq_staff_professions_business_name", table_name="staff_professions"
    )
    op.drop_table("staff_professions")
    op.drop_index("ix_staff_members_business_status_name", table_name="staff_members")
    op.drop_index("uq_staff_members_business_login", table_name="staff_members")
    op.drop_index("uq_staff_members_business_legacy", table_name="staff_members")
    op.drop_table("staff_members")
