"""Admin paneli: alohida challenge va sessiya jadvallari.

Yangi backendda admin tushunchasi umuman yo'q edi. Shu sababli obuna
to'lovini tasdiqlash endpointi `require_business_owner` bilan yopilgan
edi — ya'ni **har qanday biznes egasi o'zining to'lovini o'zi tasdiqlab**
bepul obuna olishi mumkin edi.

Admin sessiyasi oddiy foydalanuvchi sessiyasidan ajratiladi (v1656
`admin_auth.py` bilan bir xil): o'g'irlangan foydalanuvchi cookie'si
admin bo'limlarini ochmaydi.

`payment_requests` ga admin qarorini yozadigan ustun qo'shiladi —
`reviewed_by_account_id` faqat akkauntlar uchun, adminda akkaunt yo'q.
"""

from alembic import op
import sqlalchemy as sa


revision = "0026_admin_domain"
down_revision = "0025_dining_domain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_auth_challenges",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "attempts >= 0", name="ck_admin_auth_challenges_attempts"
        ),
    )
    op.create_index(
        "ix_admin_auth_challenges_owner",
        "admin_auth_challenges",
        ["telegram_user_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("token_hash", name="uq_admin_sessions_token"),
    )
    op.create_index(
        "ix_admin_sessions_active",
        "admin_sessions",
        ["telegram_user_id", "expires_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
        sqlite_where=sa.text("revoked_at IS NULL"),
    )

    op.add_column(
        "payment_requests",
        sa.Column("reviewed_by_admin_tg_id", sa.BigInteger()),
    )


def downgrade() -> None:
    op.drop_column("payment_requests", "reviewed_by_admin_tg_id")
    op.drop_table("admin_sessions")
    op.drop_table("admin_auth_challenges")
