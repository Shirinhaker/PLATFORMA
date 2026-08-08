"""E'lon joylash narxini v1656 qiymatiga keltirish.

0024 da `listing_publish` 15 000 so'm qilib yozilgan edi, v1656
`payments.py:57` da esa 10 000. Bu sababsiz farq — migratsiya paytida
kiritilgan xato.

Narx faqat hali tegilmagan bo'lsa tuzatiladi: admin panelida
o'zgartirilgan bo'lsa, o'sha qiymat saqlanadi.
"""

from alembic import op


revision = "0029_listing_publish_price"
down_revision = "0028_advertisement_authoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE platform_prices SET amount_uzs = 10000 "
        "WHERE price_code = 'listing_publish' AND amount_uzs = 15000"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE platform_prices SET amount_uzs = 15000 "
        "WHERE price_code = 'listing_publish' AND amount_uzs = 10000"
    )
