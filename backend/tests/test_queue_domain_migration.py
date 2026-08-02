from pathlib import Path

from app.queues.model import (
    QueueCounter,
    QueueEntry,
    QueueHistory,
    QueueProvider,
    QueueProviderService,
)


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0012_queue_domain.py"
)
ALEMBIC_ENV = MIGRATION.parents[1] / "env.py"


def test_queue_models_have_relational_constraints_and_hot_path_indexes():
    assert QueueProvider.__tablename__ == "queue_providers"
    assert QueueProviderService.__tablename__ == "queue_provider_services"
    assert QueueEntry.__tablename__ == "queue_entries"
    assert QueueHistory.__tablename__ == "queue_history"
    assert QueueCounter.__tablename__ == "queue_counters"

    provider_indexes = {index.name: index for index in QueueProvider.__table__.indexes}
    entry_indexes = {index.name: index for index in QueueEntry.__table__.indexes}
    history_indexes = {index.name: index for index in QueueHistory.__table__.indexes}
    counter_indexes = {index.name: index for index in QueueCounter.__table__.indexes}

    assert provider_indexes["uq_queue_providers_business_staff"].unique is True
    assert entry_indexes["uq_queue_entries_number"].unique is True
    assert entry_indexes["uq_queue_entries_slot"].unique is True
    assert entry_indexes["uq_queue_entries_active_customer_live"].unique is True
    assert "ix_queue_entries_business_day" in entry_indexes
    assert "ix_queue_entries_ahead" in entry_indexes
    assert "ix_queue_entries_customer_created" in entry_indexes
    assert "ix_queue_entries_catalog_item_id" in entry_indexes
    assert "ix_queue_history_queue" in history_indexes
    assert "ix_queue_history_business_account_id" in history_indexes
    assert "ix_queue_history_actor_account_id" in history_indexes
    assert "ix_queue_counters_catalog_item_id" in counter_indexes
    assert "ix_queue_counters_provider_id" in counter_indexes

    assert QueueProvider.__table__.c.business_account_id.foreign_keys
    assert QueueProviderService.__table__.c.provider_id.foreign_keys
    assert QueueProviderService.__table__.c.catalog_item_id.foreign_keys
    assert QueueEntry.__table__.c.customer_account_id.foreign_keys
    assert QueueEntry.__table__.c.provider_id.foreign_keys
    assert QueueHistory.__table__.c.queue_id.foreign_keys


def test_queue_migration_creates_schema_and_idempotent_legacy_backfill():
    source = MIGRATION.read_text(encoding="utf-8")
    upper = source.upper()

    assert 'revision = "0012_queue_domain"' in source
    assert 'down_revision = "0011_notifications_relational"' in source
    for table in (
        "queue_providers",
        "queue_provider_services",
        "queue_entries",
        "queue_history",
        "queue_counters",
    ):
        assert f'"{table}"' in source

    assert "cabinet_resources" in source
    assert "cabinet_records" in source
    assert "cabinet_record_fields" in source
    assert "business_profiles" in source
    assert "cabinet_payload" in source
    assert "medical_doctors" in source
    assert "medical_doctor_services" in source
    assert "medical_queue" in source
    assert "medical_queue_history" in source
    assert "legacy_id_map" in source
    assert "catalog_items" in source
    assert "ON CONFLICT" in upper
    assert "DO UPDATE" in upper
    assert "DO NOTHING" in upper
    assert "INSERT INTO queue_counters" in source


def test_queue_migration_preserves_tizimlashtirish_boundary_and_is_reversible():
    source = MIGRATION.read_text(encoding="utf-8")
    lowered = source.casefold()
    downgrade = source[source.index("def downgrade() -> None:") :]

    # Xodimlar faqat eski provider snapshotini o'qish uchun ishlatiladi;
    # Tizimlashtirish jadvallariga yozish taqiqlangan.
    assert "insert into staff" not in lowered
    assert "update staff" not in lowered
    assert "delete from staff" not in lowered
    for forbidden in ("kassa", "ombor", "qarz_tx", "tabel", "payroll"):
        assert forbidden not in lowered

    assert downgrade.index('drop_table("queue_history")') < downgrade.index(
        'drop_table("queue_entries")'
    )
    assert downgrade.index('drop_table("queue_provider_services")') < downgrade.index(
        'drop_table("queue_providers")'
    )
    assert downgrade.index('drop_table("queue_counters")') < downgrade.index(
        'drop_table("queue_providers")'
    )


def test_alembic_metadata_registers_queue_models():
    source = ALEMBIC_ENV.read_text(encoding="utf-8")
    assert "from app.queues import model as queues_model" in source
