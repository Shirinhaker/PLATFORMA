"""O'quvchining guruh tarixi jadvali.

Guruhdan guruhga ko'chirish uchun kerak: v1656da ko'chirish avvalgi
yozuvni yopib, yangisini ochadi. Mavjud o'quvchilar uchun boshlang'ich
yozuv o'sha yerdagi kabi seed qilinadi.
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_education_group_history"
down_revision = "0021_education_statistics"
branch_labels = None
depends_on = None


SEED_SQL = """
INSERT INTO education_student_group_history (
    business_account_id, legacy_source_id, student_id, group_id,
    started_date, ended_date, note, created_at
)
SELECT
    student.business_account_id,
    NULL,
    student.id,
    student.group_id,
    CASE WHEN length(COALESCE(student.joined_date, '')) = 10
        THEN student.joined_date
        ELSE to_char(now() + interval '5 hours', 'YYYY-MM-DD') END,
    '',
    'Boshlang''ich guruh',
    EXTRACT(EPOCH FROM now())::bigint
FROM education_students AS student
WHERE student.group_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM education_student_group_history AS history
      WHERE history.business_account_id = student.business_account_id
        AND history.student_id = student.id
  )
"""


def upgrade() -> None:
    op.create_table(
        "education_student_group_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("business_account_id", sa.BigInteger(), nullable=False),
        sa.Column("legacy_source_id", sa.BigInteger()),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("started_date", sa.String(length=20), nullable=False),
        sa.Column(
            "ended_date", sa.String(length=20), nullable=False, server_default=""
        ),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_education_student_group_history_student",
        "education_student_group_history",
        ["business_account_id", "student_id", "started_date", "id"],
    )
    op.create_index(
        "uq_education_student_group_history_legacy",
        "education_student_group_history",
        ["business_account_id", "legacy_source_id"],
        unique=True,
        postgresql_where=sa.text("legacy_source_id IS NOT NULL"),
    )
    op.execute(SEED_SQL)


def downgrade() -> None:
    op.drop_table("education_student_group_history")
