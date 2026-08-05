"""Ta'lim statistikasi uchun relatsion manbalar va indekslar.

K7 guruh, o'quvchi va kurs arizasini ko'chirdi. K9 v1656 statistikasi
foydalanadigan qolgan davomat, to'lov, o'qituvchi va maosh jadvallarini
ko'chiradi hamda K7 jadvallaridagi hisoblash maydonlarini to'ldiradi.
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_education_statistics"
down_revision = "0020_statistics_query_indexes"
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


def _source_ctes(resource_name: str) -> str:
    """Normalizatsiya qatori JSON fallbackdan ustun bo'lgan yagona manba."""
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


def _bigint(expression: str) -> str:
    return (
        f"CASE WHEN COALESCE({expression}, '') ~ '^[0-9]+$' "
        f"THEN ({expression})::bigint ELSE NULL END"
    )


def _timestamp(expression: str) -> str:
    return (
        f"CASE WHEN COALESCE({expression}, '') ~ '^[0-9]+([.][0-9]+)?$' "
        f"THEN to_timestamp(({expression})::double precision) ELSE now() END"
    )


def _optional_timestamp(expression: str) -> str:
    return (
        f"CASE WHEN COALESCE({expression}, '') ~ '^[0-9]+([.][0-9]+)?$' "
        f"AND ({expression})::double precision > 0 "
        f"THEN to_timestamp(({expression})::double precision) ELSE NULL END"
    )


TEACHER_BACKFILL_SQL = _source_ctes("education_teachers") + rf"""
INSERT INTO education_teachers (
    business_account_id, legacy_source_id, full_name, phone, specialty,
    hired_date, salary_type, salary_amount, note, status, created_at, updated_at
)
SELECT
    source.account_id,
    {_bigint("COALESCE(source.row_data->>'id', source.source_key)")},
    left(COALESCE(source.row_data->>'full_name', ''), 160),
    left(COALESCE(source.row_data->>'phone', ''), 40),
    left(COALESCE(source.row_data->>'specialty', ''), 160),
    left(COALESCE(source.row_data->>'hired_date', ''), 20),
    CASE WHEN source.row_data->>'salary_type' IN ('monthly', 'per_lesson')
        THEN source.row_data->>'salary_type' ELSE 'monthly' END,
    COALESCE({_bigint("source.row_data->>'salary_amount'")}, 0),
    COALESCE(source.row_data->>'note', ''),
    left(COALESCE(NULLIF(source.row_data->>'status', ''), 'active'), 20),
    {_timestamp("source.row_data->>'created_at'")},
    {_timestamp("source.row_data->>'updated_at'")}
FROM source_rows AS source
WHERE COALESCE(source.row_data->>'id', source.source_key, '') ~ '^[0-9]+$'
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO UPDATE SET
    full_name = EXCLUDED.full_name,
    phone = EXCLUDED.phone,
    specialty = EXCLUDED.specialty,
    hired_date = EXCLUDED.hired_date,
    salary_type = EXCLUDED.salary_type,
    salary_amount = EXCLUDED.salary_amount,
    note = EXCLUDED.note,
    status = EXCLUDED.status,
    updated_at = EXCLUDED.updated_at
"""


GROUP_DETAILS_BACKFILL_SQL = _source_ctes("education_groups") + rf"""
UPDATE education_groups AS target
SET
    legacy_teacher_id = {_bigint("source.row_data->>'teacher_id'")},
    teacher_id = teacher.id,
    teacher_name = left(COALESCE(source.row_data->>'teacher_name', ''), 160),
    room_name = left(COALESCE(source.row_data->>'room_name', ''), 80),
    capacity = COALESCE({_bigint("source.row_data->>'capacity'")}, 0)::integer,
    weekdays = left(COALESCE(source.row_data->>'weekdays', ''), 64),
    lesson_from = left(COALESCE(source.row_data->>'lesson_from', ''), 5),
    lesson_to = left(COALESCE(source.row_data->>'lesson_to', ''), 5),
    start_date = left(COALESCE(source.row_data->>'start_date', ''), 20),
    end_date = left(COALESCE(source.row_data->>'end_date', ''), 20),
    billing_type = CASE WHEN source.row_data->>'billing_type' = 'attendance'
        THEN 'attendance' ELSE 'monthly' END,
    package_lessons = COALESCE(
        {_bigint("source.row_data->>'package_lessons'")}, 0
    )::integer,
    package_price = COALESCE(
        {_bigint("source.row_data->>'package_price'")}, 0
    )
FROM source_rows AS source
LEFT JOIN education_teachers AS teacher
    ON teacher.business_account_id = source.account_id
   AND teacher.legacy_source_id = {_bigint("source.row_data->>'teacher_id'")}
WHERE target.business_account_id = source.account_id
  AND target.legacy_source_id
      = {_bigint("COALESCE(source.row_data->>'id', source.source_key)")}
"""


STUDENT_DETAILS_BACKFILL_SQL = _source_ctes("education_students") + rf"""
UPDATE education_students AS target
SET
    parent_name = left(COALESCE(source.row_data->>'parent_name', ''), 160),
    parent_phone = left(COALESCE(source.row_data->>'parent_phone', ''), 40),
    birth_date = left(COALESCE(source.row_data->>'birth_date', ''), 20),
    payment_start_date = left(
        COALESCE(source.row_data->>'payment_start_date', ''), 20
    ),
    lesson_package_override = COALESCE(
        {_bigint("source.row_data->>'lesson_package_override'")}, 0
    )::integer
FROM source_rows AS source
WHERE target.business_account_id = source.account_id
  AND target.legacy_source_id
      = {_bigint("COALESCE(source.row_data->>'id', source.source_key)")}
"""


ATTENDANCE_BACKFILL_SQL = _source_ctes("education_attendance") + rf"""
INSERT INTO education_attendance (
    business_account_id, legacy_source_id, group_id, student_id,
    legacy_group_id, legacy_student_id, lesson_date, attendance_status,
    note, created_at, updated_at
)
SELECT
    source.account_id,
    {_bigint("COALESCE(source.row_data->>'id', source.source_key)")},
    grp.id,
    student.id,
    {_bigint("source.row_data->>'group_id'")},
    {_bigint("source.row_data->>'student_id'")},
    left(COALESCE(source.row_data->>'lesson_date', ''), 10),
    CASE WHEN source.row_data->>'attendance_status'
        IN ('present', 'late', 'excused', 'absent')
        THEN source.row_data->>'attendance_status' ELSE 'present' END,
    COALESCE(source.row_data->>'note', ''),
    {_timestamp("source.row_data->>'created_at'")},
    {_timestamp("source.row_data->>'updated_at'")}
FROM source_rows AS source
LEFT JOIN education_groups AS grp
    ON grp.business_account_id = source.account_id
   AND grp.legacy_source_id = {_bigint("source.row_data->>'group_id'")}
LEFT JOIN education_students AS student
    ON student.business_account_id = source.account_id
   AND student.legacy_source_id = {_bigint("source.row_data->>'student_id'")}
WHERE COALESCE(source.row_data->>'id', source.source_key, '') ~ '^[0-9]+$'
  AND COALESCE(source.row_data->>'lesson_date', '') <> ''
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO UPDATE SET
    group_id = EXCLUDED.group_id,
    student_id = EXCLUDED.student_id,
    lesson_date = EXCLUDED.lesson_date,
    attendance_status = EXCLUDED.attendance_status,
    note = EXCLUDED.note,
    updated_at = EXCLUDED.updated_at
"""


PAYMENT_BACKFILL_SQL = _source_ctes("education_payments") + rf"""
INSERT INTO education_payments (
    business_account_id, legacy_source_id, student_id, legacy_student_id,
    payment_month, amount, pay_type, note, legacy_sale_id, voided_at,
    legacy_voided_by, void_reason, created_at
)
SELECT
    source.account_id,
    {_bigint("COALESCE(source.row_data->>'id', source.source_key)")},
    student.id,
    {_bigint("source.row_data->>'student_id'")},
    left(COALESCE(source.row_data->>'payment_month', ''), 7),
    COALESCE({_bigint("source.row_data->>'amount'")}, 0),
    CASE WHEN source.row_data->>'pay_type' = 'karta'
        THEN 'karta' ELSE 'naqd' END,
    COALESCE(source.row_data->>'note', ''),
    {_bigint("source.row_data->>'sale_id'")},
    {_optional_timestamp("source.row_data->>'voided_at'")},
    {_bigint("source.row_data->>'voided_by'")},
    COALESCE(source.row_data->>'void_reason', ''),
    {_timestamp("source.row_data->>'created_at'")}
FROM source_rows AS source
LEFT JOIN education_students AS student
    ON student.business_account_id = source.account_id
   AND student.legacy_source_id = {_bigint("source.row_data->>'student_id'")}
WHERE COALESCE(source.row_data->>'id', source.source_key, '') ~ '^[0-9]+$'
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO UPDATE SET
    student_id = EXCLUDED.student_id,
    payment_month = EXCLUDED.payment_month,
    amount = EXCLUDED.amount,
    pay_type = EXCLUDED.pay_type,
    note = EXCLUDED.note,
    voided_at = EXCLUDED.voided_at,
    legacy_voided_by = EXCLUDED.legacy_voided_by,
    void_reason = EXCLUDED.void_reason
"""


TEACHER_PAYMENT_BACKFILL_SQL = _source_ctes(
    "education_teacher_payments"
) + rf"""
INSERT INTO education_teacher_payments (
    business_account_id, legacy_source_id, teacher_id, legacy_teacher_id,
    payment_month, amount, pay_type, note, expense_id, legacy_expense_id,
    created_at
)
SELECT
    source.account_id,
    {_bigint("COALESCE(source.row_data->>'id', source.source_key)")},
    teacher.id,
    {_bigint("source.row_data->>'teacher_id'")},
    left(COALESCE(source.row_data->>'payment_month', ''), 7),
    COALESCE({_bigint("source.row_data->>'amount'")}, 0),
    CASE WHEN source.row_data->>'pay_type' = 'karta'
        THEN 'karta' ELSE 'naqd' END,
    COALESCE(source.row_data->>'note', ''),
    expense.id,
    {_bigint("source.row_data->>'expense_id'")},
    {_timestamp("source.row_data->>'created_at'")}
FROM source_rows AS source
LEFT JOIN education_teachers AS teacher
    ON teacher.business_account_id = source.account_id
   AND teacher.legacy_source_id = {_bigint("source.row_data->>'teacher_id'")}
LEFT JOIN expenses AS expense
    ON expense.business_account_id = source.account_id
   AND expense.legacy_source_id = {_bigint("source.row_data->>'expense_id'")}
WHERE COALESCE(source.row_data->>'id', source.source_key, '') ~ '^[0-9]+$'
ON CONFLICT (business_account_id, legacy_source_id)
    WHERE legacy_source_id IS NOT NULL
DO UPDATE SET
    teacher_id = EXCLUDED.teacher_id,
    payment_month = EXCLUDED.payment_month,
    amount = EXCLUDED.amount,
    pay_type = EXCLUDED.pay_type,
    note = EXCLUDED.note,
    expense_id = EXCLUDED.expense_id
"""


def upgrade() -> None:
    op.add_column("education_groups", sa.Column("legacy_teacher_id", sa.BigInteger()))
    op.add_column(
        "education_groups",
        sa.Column("teacher_name", sa.String(length=160), nullable=False, server_default=""),
    )
    op.add_column(
        "education_groups",
        sa.Column("room_name", sa.String(length=80), nullable=False, server_default=""),
    )
    op.add_column(
        "education_groups",
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "education_groups",
        sa.Column("weekdays", sa.String(length=64), nullable=False, server_default=""),
    )
    op.add_column(
        "education_groups",
        sa.Column("lesson_from", sa.String(length=5), nullable=False, server_default=""),
    )
    op.add_column(
        "education_groups",
        sa.Column("lesson_to", sa.String(length=5), nullable=False, server_default=""),
    )
    op.add_column(
        "education_groups",
        sa.Column("start_date", sa.String(length=20), nullable=False, server_default=""),
    )
    op.add_column(
        "education_groups",
        sa.Column("end_date", sa.String(length=20), nullable=False, server_default=""),
    )
    op.add_column(
        "education_groups",
        sa.Column("billing_type", sa.String(length=20), nullable=False, server_default="monthly"),
    )
    op.add_column(
        "education_groups",
        sa.Column("package_lessons", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "education_groups",
        sa.Column("package_price", sa.BigInteger(), nullable=False, server_default="0"),
    )

    op.add_column(
        "education_students",
        sa.Column("parent_name", sa.String(length=160), nullable=False, server_default=""),
    )
    op.add_column(
        "education_students",
        sa.Column("parent_phone", sa.String(length=40), nullable=False, server_default=""),
    )
    op.add_column(
        "education_students",
        sa.Column("birth_date", sa.String(length=20), nullable=False, server_default=""),
    )
    op.add_column(
        "education_students",
        sa.Column("payment_start_date", sa.String(length=20), nullable=False, server_default=""),
    )
    op.add_column(
        "education_students",
        sa.Column("lesson_package_override", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "education_teachers",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("full_name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("specialty", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("hired_date", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("salary_type", sa.String(length=20), nullable=False, server_default="monthly"),
        sa.Column("salary_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("salary_type IN ('monthly', 'per_lesson')", name="ck_education_teachers_salary_type"),
        sa.CheckConstraint("salary_amount >= 0", name="ck_education_teachers_salary_amount"),
        sa.ForeignKeyConstraint(["business_account_id"], ["accounts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_education_teachers_business", "education_teachers", ["business_account_id", "status", "id"])
    op.create_index(
        "uq_education_teachers_legacy",
        "education_teachers",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )

    op.create_table(
        "education_attendance",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("group_id", sa.BigInteger()),
        sa.Column("student_id", sa.BigInteger()),
        sa.Column("legacy_group_id", sa.BigInteger()),
        sa.Column("legacy_student_id", sa.BigInteger()),
        sa.Column("lesson_date", sa.String(length=10), nullable=False),
        sa.Column("attendance_status", sa.String(length=20), nullable=False, server_default="present"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attendance_status IN ('present', 'late', 'excused', 'absent')", name="ck_education_attendance_status"),
        sa.ForeignKeyConstraint(["business_account_id"], ["accounts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_education_attendance_business_date", "education_attendance", ["business_account_id", "lesson_date", "group_id"])
    op.create_index("ix_education_attendance_student_date", "education_attendance", ["business_account_id", "student_id", "lesson_date"])
    op.create_index(
        "uq_education_attendance_legacy",
        "education_attendance",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.create_index(
        "uq_education_attendance_day",
        "education_attendance",
        ["business_account_id", "group_id", "student_id", "lesson_date"],
        unique=True,
        postgresql_where=sa.text("group_id IS NOT NULL AND student_id IS NOT NULL"),
    )

    op.create_table(
        "education_payments",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("student_id", sa.BigInteger()),
        sa.Column("legacy_student_id", sa.BigInteger()),
        sa.Column("payment_month", sa.String(length=7), nullable=False, server_default=""),
        sa.Column("amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("pay_type", sa.String(length=20), nullable=False, server_default="naqd"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("legacy_sale_id", sa.BigInteger()),
        sa.Column("voided_at", sa.DateTime(timezone=True)),
        sa.Column("legacy_voided_by", sa.BigInteger()),
        sa.Column("void_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_education_payments_amount"),
        sa.ForeignKeyConstraint(["business_account_id"], ["accounts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_education_payments_business_created", "education_payments", ["business_account_id", "created_at", "id"])
    op.create_index("ix_education_payments_student_month", "education_payments", ["business_account_id", "student_id", "payment_month", "id"])
    op.create_index(
        "uq_education_payments_legacy",
        "education_payments",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )

    op.create_table(
        "education_teacher_payments",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("teacher_id", sa.BigInteger()),
        sa.Column("legacy_teacher_id", sa.BigInteger()),
        sa.Column("payment_month", sa.String(length=7), nullable=False, server_default=""),
        sa.Column("amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("pay_type", sa.String(length=20), nullable=False, server_default="naqd"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("expense_id", sa.BigInteger()),
        sa.Column("legacy_expense_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_education_teacher_payments_amount"),
        sa.ForeignKeyConstraint(["business_account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_education_teacher_payments_business_created", "education_teacher_payments", ["business_account_id", "created_at", "id"])
    op.create_index("ix_education_teacher_payments_teacher_month", "education_teacher_payments", ["business_account_id", "teacher_id", "payment_month", "id"])
    op.create_index(
        "uq_education_teacher_payments_legacy",
        "education_teacher_payments",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )

    op.execute(TEACHER_BACKFILL_SQL)
    op.execute(GROUP_DETAILS_BACKFILL_SQL)
    op.execute(STUDENT_DETAILS_BACKFILL_SQL)
    op.execute(ATTENDANCE_BACKFILL_SQL)
    op.execute(PAYMENT_BACKFILL_SQL)
    op.execute(TEACHER_PAYMENT_BACKFILL_SQL)


def downgrade() -> None:
    op.drop_table("education_teacher_payments")
    op.drop_table("education_payments")
    op.drop_table("education_attendance")
    op.drop_table("education_teachers")

    for column in (
        "lesson_package_override",
        "payment_start_date",
        "birth_date",
        "parent_phone",
        "parent_name",
    ):
        op.drop_column("education_students", column)
    for column in (
        "package_price",
        "package_lessons",
        "billing_type",
        "end_date",
        "start_date",
        "lesson_to",
        "lesson_from",
        "weekdays",
        "capacity",
        "room_name",
        "teacher_name",
        "legacy_teacher_id",
    ):
        op.drop_column("education_groups", column)
