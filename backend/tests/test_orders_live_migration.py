from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0009_orders_live_v1656.py"
)
ALEMBIC_ENV = MIGRATION.parents[1] / "env.py"


def test_order_migration_creates_live_tables_constraints_and_indexes():
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "0009_orders_live_v1656"' in source
    assert 'down_revision = "0008_listings_live_v1656"' in source
    assert 'op.create_table(\n        "orders"' in source
    assert 'op.create_table(\n        "order_items"' in source
    assert 'op.create_table(\n        "order_messages"' in source
    assert "ck_orders_status" in source
    assert "ck_orders_payment_status" in source
    assert "ix_orders_customer_created" in source
    assert "ix_orders_provider_created" in source
    assert "ix_orders_provider_unread" in source
    assert "ix_orders_customer_unread" in source
    assert "ix_order_items_order" in source
    assert "ix_order_messages_order_created" in source


def test_order_migration_backfills_v7_orders_items_and_messages_idempotently():
    source = MIGRATION.read_text(encoding="utf-8")
    upper = source.upper()

    assert "user_profiles" in source
    assert "business_profiles" in source
    assert "cabinet_payload" in source
    assert "cabinet_resources" in source
    assert "legacy_id_map" in source
    assert "user_account" in source
    assert "business_account" in source
    assert "catalog_item" in source
    assert "listing" in source
    assert "jsonb_array_elements" in source
    assert "legacy_source_id" in source
    assert "INSERT INTO orders" in source
    assert "INSERT INTO order_items" in source
    assert "INSERT INTO order_messages" in source
    assert "ON CONFLICT" in upper
    assert "DO UPDATE" in upper
    assert "DO NOTHING" in upper


def test_order_migration_does_not_write_tizimlashtirish_modules_and_is_reversible():
    source = MIGRATION.read_text(encoding="utf-8")
    lowered = source.casefold()
    downgrade = source[source.index("def downgrade() -> None:"):]

    assert "kassa" not in lowered
    assert "ombor" not in lowered
    assert "qarz_tx" not in lowered
    assert downgrade.index('drop_table("order_messages")') < downgrade.index(
        'drop_table("orders")'
    )
    assert downgrade.index('drop_table("order_items")') < downgrade.index(
        'drop_table("orders")'
    )


def test_alembic_metadata_registers_order_models():
    source = ALEMBIC_ENV.read_text(encoding="utf-8")
    assert "from app.orders import model as orders_model" in source
