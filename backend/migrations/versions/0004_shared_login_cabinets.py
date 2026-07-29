from alembic import op
import sqlalchemy as sa


revision = "0004_shared_login_cabinets"
down_revision = "0003_phase3c_content"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("accounts_login_key", "accounts", type_="unique")
    op.create_index(
        "uq_accounts_login_type_lower",
        "accounts",
        [sa.text("lower(login)"), "account_type"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_accounts_login_type_lower", table_name="accounts")
    op.create_unique_constraint("accounts_login_key", "accounts", ["login"])
