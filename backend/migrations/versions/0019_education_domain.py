"""Ta'lim domeni: guruhlar, o'quvchilar va kurs arizalari.

Ariza avval o'quv markazining profil qatorini qulflab, butun arizalar
ro'yxatini qayta yozardi. Endi har ariza — alohida jadvalga bitta
INSERT, takroriylik esa qisman noyob indeks bilan to'siladi.

Eski `id` qiymatlari har biznes ichida qaytadan boshlanadi, shuning
uchun ular global birlamchi kalit bo'la olmaydi. Ular
`legacy_source_id` da saqlanadi, guruhga havolalar esa INSERT paytida
yangi kalitlarga bog'lanadi — shu sababli backfill takroran ishga
tushirilsa ham natija o'zgarmaydi.
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_education_domain"
down_revision = "0018_expense_domain"
branch_labels = None
depends_on = None


JSON_VALUE_SQL = r"""
CASE
    WHEN field.value_type = 'number' THEN to_jsonb(field.number_value)
    WHEN field.value_type = 'bool' THEN to_jsonb(field.bool_value)
    WHEN field.value_type = 'null' THEN 'null'::jsonb
    ELSE to_jsonb(field.text_value)
END
"""


def _source_ctes(resource_name: str) -> str:
    """`cabinet_records` va `cabinet_payload` dan birlashtirilgan manba.

    Ikkalasida ham bor yozuv uchun relatsion nusxa ustun turadi.
    """
    return rf"""WITH
relational_rows AS (
    SELECT
        resource.account_id,
        record.source_key,
        record.ordinal,
        COALESCE(
            jsonb_object_agg(substr(field.path, 2), {JSON_VALUE_SQL})
                FILTER (WHERE field.path ~ '^/[^/]+$'),
            '{{}}'::jsonb
        ) AS row_data,
        0 AS priority
    FROM cabinet_resources AS resource
    JOIN cabinet_records AS record ON record.resource_id = resource.id
    LEFT JOIN cabinet_record_fields AS field ON field.record_id = record.id
    WHERE resource.account_type = 'business'
      AND resource.resource = '{resource_name}'
    GROUP BY resource.account_id, record.id, record.source_key, record.ordinal
),
payload_rows AS (
    SELECT
        profile.account_id,
        COALESCE(NULLIF(entry.row_data->>'id', ''), 'ordinal:' || entry.ordinality)
            AS source_key,
        entry.ordinality::integer AS ordinal,
        entry.row_data,
        1 AS priority
    FROM business_profiles AS profile
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(
            COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
            -> '{resource_name}'
        ) = 'array'
        THEN COALESCE(profile.cabinet_payload::jsonb, '{{}}'::jsonb)
            -> '{resource_name}'
        ELSE '[]'::jsonb END
    ) WITH ORDINALITY AS entry(row_data, ordinality)
),
source_rows AS (
    SELECT DISTINCT ON (account_id, source_key)
        account_id, source_key, ordinal, row_data
    FROM (
        SELECT * FROM relational_rows
        UNION ALL
        SELECT * FROM payload_rows
    ) AS candidates
    ORDER BY account_id, source_key, priority, ordinal
)
"""


# Eski qatorlarda son maydonlar matn bo'lib kelishi mumkin.
def _bigint(expression: str) -> str:
    return (
        f"CASE WHEN COALESCE({expression}, '') ~ '^[0-9]+$' "
        f"THEN ({expression})::bigint ELSE NULL END"
    )


def _timestamp(expression: str) -> str:
    return (
        f"CASE WHEN COALESCE({expression}, '') ~ '^[0-9]+([.][0-9]+)?$' "
        f"THEN ({expression})::double precision::bigint "
        f"ELSE EXTRACT(EPOCH FROM now())::bigint END"
    )


GROUP_BACKFILL_SQL = _source_ctes("education_groups") + rf"""
INSERT INTO education_groups (
    business_account_id, legacy_source_id, course_item_id, name,
    teacher_id, status, created_at, updated_at
)
SELECT
    source.account_id,
    {_bigint("COALESCE(source.row_data->>'id', source.source_key)")},
    {_bigint("source.row_data->>'course_item_id'")},
    left(trim(source.row_data->>'name'), 160),
    {_bigint("source.row_data->>'teacher_id'")},
    left(COALESCE(NULLIF(source.row_data->>'status', ''), 'active'), 20),
    {_timestamp("source.row_data->>'created_at'")},
    {_timestamp("source.row_data->>'updated_at'")}
FROM source_rows AS source
WHERE length(trim(COALESCE(source.row_data->>'name', ''))) > 0
  AND COALESCE(source.row_data->>'id', source.source_key, '') ~ '^[0-9]+$'
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO UPDATE SET
    course_item_id = EXCLUDED.course_item_id,
    name = EXCLUDED.name,
    teacher_id = EXCLUDED.teacher_id,
    status = EXCLUDED.status,
    updated_at = EXCLUDED.updated_at
"""


STUDENT_BACKFILL_SQL = _source_ctes("education_students") + rf"""
INSERT INTO education_students (
    business_account_id, legacy_source_id, group_id, user_account_id,
    legacy_user_id, full_name, phone, joined_date, note, monthly_fee,
    status, created_at, updated_at
)
SELECT
    source.account_id,
    {_bigint("COALESCE(source.row_data->>'id', source.source_key)")},
    grp.id,
    {_bigint("source.row_data->>'user_account_id'")},
    {_bigint("source.row_data->>'user_id'")},
    left(COALESCE(source.row_data->>'full_name', ''), 160),
    left(COALESCE(source.row_data->>'phone', ''), 40),
    left(COALESCE(source.row_data->>'joined_date', ''), 20),
    COALESCE(source.row_data->>'note', ''),
    COALESCE({_bigint("source.row_data->>'monthly_fee'")}, 0),
    left(COALESCE(NULLIF(source.row_data->>'status', ''), 'active'), 20),
    {_timestamp("source.row_data->>'created_at'")},
    {_timestamp("source.row_data->>'updated_at'")}
FROM source_rows AS source
LEFT JOIN education_groups AS grp
    ON grp.business_account_id = source.account_id
   AND grp.legacy_source_id
       = {_bigint("source.row_data->>'group_id'")}
WHERE COALESCE(source.row_data->>'id', source.source_key, '') ~ '^[0-9]+$'
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO UPDATE SET
    group_id = EXCLUDED.group_id,
    phone = EXCLUDED.phone,
    status = EXCLUDED.status,
    updated_at = EXCLUDED.updated_at
"""


ENROLLMENT_BACKFILL_SQL = _source_ctes("education_enrollments") + rf"""
INSERT INTO course_enrollments (
    business_account_id, legacy_source_id, legacy_business_id,
    course_item_id, user_account_id, legacy_user_id, customer_name,
    phone, note, status, group_id, created_at, updated_at
)
SELECT
    source.account_id,
    {_bigint("COALESCE(source.row_data->>'id', source.source_key)")},
    {_bigint("source.row_data->>'business_id'")},
    COALESCE({_bigint("source.row_data->>'course_item_id'")}, 0),
    {_bigint("source.row_data->>'user_account_id'")},
    NULLIF(COALESCE({_bigint("source.row_data->>'user_legacy_id'")}, 0), 0),
    left(COALESCE(source.row_data->>'customer_name', ''), 160),
    left(COALESCE(source.row_data->>'phone', ''), 40),
    COALESCE(source.row_data->>'note', ''),
    CASE WHEN source.row_data->>'status'
        IN ('new', 'accepted', 'rejected')
        THEN source.row_data->>'status' ELSE 'new' END,
    grp.id,
    {_timestamp("source.row_data->>'created_at'")},
    {_timestamp("source.row_data->>'updated_at'")}
FROM source_rows AS source
LEFT JOIN education_groups AS grp
    ON grp.business_account_id = source.account_id
   AND grp.legacy_source_id
       = {_bigint("source.row_data->>'group_id'")}
WHERE COALESCE(source.row_data->>'id', source.source_key, '') ~ '^[0-9]+$'
  AND COALESCE({_bigint("source.row_data->>'course_item_id'")}, 0) > 0
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO UPDATE SET
    status = EXCLUDED.status,
    group_id = EXCLUDED.group_id,
    phone = EXCLUDED.phone,
    updated_at = EXCLUDED.updated_at
"""


def upgrade() -> None:
    op.create_table(
        "education_groups",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("course_item_id", sa.BigInteger()),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("teacher_id", sa.BigInteger()),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="active"
        ),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_education_groups_name_required",
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_education_groups_business",
        "education_groups",
        ["business_account_id", "status", "id"],
    )
    op.create_index(
        "uq_education_groups_legacy",
        "education_groups",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )

    op.create_table(
        "education_students",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("group_id", sa.BigInteger()),
        sa.Column("user_account_id", sa.BigInteger()),
        sa.Column("legacy_user_id", sa.BigInteger()),
        sa.Column(
            "full_name", sa.String(length=160), nullable=False, server_default=""
        ),
        sa.Column("phone", sa.String(length=40), nullable=False, server_default=""),
        sa.Column(
            "joined_date", sa.String(length=20), nullable=False, server_default=""
        ),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "monthly_fee", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="active"
        ),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "monthly_fee >= 0", name="ck_education_students_monthly_fee"
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_account_id"], ["accounts.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_education_students_business",
        "education_students",
        ["business_account_id", "status", "id"],
    )
    op.create_index(
        "ix_education_students_group",
        "education_students",
        ["business_account_id", "group_id"],
    )
    op.create_index(
        "uq_education_students_legacy",
        "education_students",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )

    op.create_table(
        "course_enrollments",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("legacy_business_id", sa.BigInteger()),
        sa.Column("course_item_id", sa.BigInteger(), nullable=False),
        sa.Column("user_account_id", sa.BigInteger()),
        sa.Column("legacy_user_id", sa.BigInteger()),
        sa.Column(
            "customer_name", sa.String(length=160), nullable=False, server_default=""
        ),
        sa.Column("phone", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="new"
        ),
        sa.Column("group_id", sa.BigInteger()),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "status IN ('new', 'accepted', 'rejected')",
            name="ck_course_enrollments_status",
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_account_id"], ["accounts.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_course_enrollments_business",
        "course_enrollments",
        ["business_account_id", "status", "id"],
    )
    op.create_index(
        "uq_course_enrollments_legacy",
        "course_enrollments",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "uq_course_enrollments_active_account",
        "course_enrollments",
        ["business_account_id", "course_item_id", "user_account_id"],
        unique=True,
        postgresql_where=sa.text(
            "user_account_id IS NOT NULL AND status IN ('new', 'accepted')"
        ),
    )
    op.create_index(
        "uq_course_enrollments_active_legacy_user",
        "course_enrollments",
        ["business_account_id", "course_item_id", "legacy_user_id"],
        unique=True,
        postgresql_where=sa.text(
            "legacy_user_id IS NOT NULL AND status IN ('new', 'accepted')"
        ),
    )

    # Guruhlar birinchi: o'quvchi va ariza havolalari shu yerdan bog'lanadi.
    op.execute(GROUP_BACKFILL_SQL)
    op.execute(STUDENT_BACKFILL_SQL)
    op.execute(ENROLLMENT_BACKFILL_SQL)


def downgrade() -> None:
    op.drop_table("course_enrollments")
    op.drop_table("education_students")
    op.drop_table("education_groups")
