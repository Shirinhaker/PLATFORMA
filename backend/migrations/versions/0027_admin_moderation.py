"""Moderatsiya, shikoyatlar va o'zgartirib bo'lmaydigan audit tarixi.

A1 da admin sessiyasi va to'lov navbati qo'shilgan edi. Bu migratsiya
v1656 admin saytining qolgan qismini beradi: akkaunt cheklovlari, ichki
izohlar, kontent ko'rinishi, shikoyatlar navbati va audit jurnali.

Audit jurnali faqat qo'shiladi. v1656 da buni SQLite triggerlari
himoyalagan; bu yerda `plpgsql` funksiyasi bilan — ya'ni `UPDATE` yoki
`DELETE` bazaning o'zida rad etiladi, ilova kodiga ishonilmaydi.
"""

from alembic import op
import sqlalchemy as sa


revision = "0027_admin_moderation"
down_revision = "0026_admin_domain"
branch_labels = None
depends_on = None


APPEND_ONLY_FUNCTION = """
CREATE OR REPLACE FUNCTION admin_audit_append_only()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'admin audit is append-only';
END;
$$ LANGUAGE plpgsql
"""

APPEND_ONLY_UPDATE_TRIGGER = """
CREATE TRIGGER admin_audit_no_update
BEFORE UPDATE ON admin_audit_log
FOR EACH ROW EXECUTE FUNCTION admin_audit_append_only()
"""

APPEND_ONLY_DELETE_TRIGGER = """
CREATE TRIGGER admin_audit_no_delete
BEFORE DELETE ON admin_audit_log
FOR EACH ROW EXECUTE FUNCTION admin_audit_append_only()
"""


def upgrade() -> None:
    op.create_table(
        "account_restrictions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=False),
        sa.Column("restriction", sa.String(length=32), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False,
            server_default="active",
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_by_tg_id", sa.BigInteger()),
        sa.Column(
            "revoked_reason", sa.Text(), nullable=False, server_default=""
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "actor_type IN ('user', 'business')",
            name="ck_account_restrictions_actor",
        ),
        sa.CheckConstraint(
            "restriction IN ('content_hidden', 'account_blocked')",
            name="ck_account_restrictions_kind",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_account_restrictions_status",
        ),
    )
    op.create_index(
        "uq_account_restriction_active",
        "account_restrictions",
        ["actor_type", "actor_id", "restriction"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_account_restrictions_lookup",
        "account_restrictions",
        ["actor_type", "actor_id", "status"],
    )

    op.create_table(
        "admin_account_notes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("admin_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('user', 'business')",
            name="ck_admin_account_notes_actor",
        ),
    )
    op.create_index(
        "ix_admin_account_notes_actor",
        "admin_account_notes",
        ["actor_type", "actor_id", sa.text("id DESC")],
    )

    op.create_table(
        "content_moderation",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("content_kind", sa.String(length=32), nullable=False),
        sa.Column("content_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changed_by_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('hidden', 'visible', 'removed')",
            name="ck_content_moderation_status",
        ),
    )
    op.create_index(
        "ix_content_moderation_latest",
        "content_moderation",
        ["content_kind", "content_id", sa.text("id DESC")],
    )

    op.create_table(
        "moderation_reports",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("reporter_account_id", sa.BigInteger(), nullable=False),
        sa.Column("content_kind", sa.String(length=32), nullable=False),
        sa.Column("content_id", sa.BigInteger(), nullable=False),
        sa.Column("reason_code", sa.String(length=16), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "status", sa.String(length=16), nullable=False,
            server_default="open",
        ),
        sa.Column("assigned_admin_tg_id", sa.BigInteger()),
        sa.Column("resolution", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('open', 'reviewing', 'resolved', 'dismissed')",
            name="ck_moderation_reports_status",
        ),
        sa.CheckConstraint(
            "reason_code IN ('fraud', 'spam', 'illegal', 'abuse', 'other')",
            name="ck_moderation_reports_reason",
        ),
    )
    op.create_index(
        "ix_moderation_reports_queue",
        "moderation_reports",
        ["status", "created_at", "id"],
    )
    op.create_index(
        "ix_moderation_reports_content",
        "moderation_reports",
        ["content_kind", "content_id"],
    )

    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("admin_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_kind", sa.String(length=40), nullable=False),
        sa.Column(
            "target_id", sa.String(length=64), nullable=False,
            server_default="",
        ),
        sa.Column(
            "before_json", sa.JSON(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "after_json", sa.JSON(), nullable=False, server_default="{}"
        ),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "ip_hash", sa.String(length=128), nullable=False,
            server_default="",
        ),
        sa.Column(
            "user_agent", sa.String(length=500), nullable=False,
            server_default="",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_admin_audit_action_created",
        "admin_audit_log",
        ["action", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_admin_audit_admin_created",
        "admin_audit_log",
        ["admin_tg_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )

    if op.get_bind().dialect.name != "postgresql":
        return
    # Har bir `op.execute` — bitta bayonot.
    op.execute(APPEND_ONLY_FUNCTION)
    op.execute(APPEND_ONLY_UPDATE_TRIGGER)
    op.execute(APPEND_ONLY_DELETE_TRIGGER)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS admin_audit_no_delete ON admin_audit_log")
        op.execute("DROP TRIGGER IF EXISTS admin_audit_no_update ON admin_audit_log")
        op.execute("DROP FUNCTION IF EXISTS admin_audit_append_only()")
    op.drop_table("admin_audit_log")
    op.drop_table("moderation_reports")
    op.drop_table("content_moderation")
    op.drop_table("admin_account_notes")
    op.drop_table("account_restrictions")
