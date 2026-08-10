"""Ta'lim boshqaruvini typed modulga yakuniy ko'chirish.

Revision ID: 0034_education_management
Revises: 0033_notifications_v1656

Yangi o'quvchi to'lovi Kassa bilan bitta tranzaksiyada yoziladi. Eski
to'lovlar 0016 migratsiyasida yaratilgan kassa satri orqali bog'lanadi.
"""

from alembic import op
import sqlalchemy as sa


revision = "0034_education_management"
down_revision = "0033_notifications_v1656"
branch_labels = None
depends_on = None


BACKFILL_CASH_RECEIPT_SQL = r"""
UPDATE education_payments AS payment
SET cash_receipt_id = receipt_line.receipt_id
FROM cash_receipt_lines AS receipt_line
WHERE payment.cash_receipt_id IS NULL
  AND payment.legacy_sale_id IS NOT NULL
  AND receipt_line.business_account_id = payment.business_account_id
  AND receipt_line.legacy_source_key = 'sales:' || payment.legacy_sale_id::text
"""


def upgrade() -> None:
    op.add_column(
        "education_payments",
        sa.Column("cash_receipt_id", sa.BigInteger()),
    )
    op.create_foreign_key(
        "fk_education_payments_cash_receipt",
        "education_payments",
        "cash_receipts",
        ["cash_receipt_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_education_payments_cash_receipt",
        "education_payments",
        ["cash_receipt_id"],
        unique=True,
        postgresql_where=sa.text("cash_receipt_id IS NOT NULL"),
    )
    op.execute(BACKFILL_CASH_RECEIPT_SQL)


def downgrade() -> None:
    op.drop_index(
        "uq_education_payments_cash_receipt",
        table_name="education_payments",
    )
    op.drop_constraint(
        "fk_education_payments_cash_receipt",
        "education_payments",
        type_="foreignkey",
    )
    op.drop_column("education_payments", "cash_receipt_id")
