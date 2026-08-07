"""Reklama joylash: yangi reklama migratsiya yozuvisiz yaratiladi.

Reklama joylash oqimi ko'chirilmagan edi: `advertisements` jadvalini
faqat eski ma'lumot ko'chiruvchi to'ldirardi, yangi reklama esa kabinet
JSON'iga tushardi. Public reklamalar shu jadvaldan o'qilgani uchun
yangi reklama hech qachon bosh sahifada chiqmasdi.

`migration_run_id` majburiy edi — bu faqat ko'chirilgan yozuvlar uchun
mantiqiy. E'lonlarda u allaqachon ixtiyoriy; reklama ham shunday
bo'ladi.
"""

from alembic import op
import sqlalchemy as sa


revision = "0028_advertisement_authoring"
down_revision = "0027_admin_moderation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "advertisements",
        "migration_run_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    # Ko'chirilmagan reklamalar bo'lsa, ustunni qaytarib majburiy
    # qilib bo'lmaydi — avval ular o'chirilishi kerak.
    op.execute("DELETE FROM advertisements WHERE migration_run_id IS NULL")
    op.alter_column(
        "advertisements",
        "migration_run_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
