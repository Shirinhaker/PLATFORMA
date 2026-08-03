import importlib.util
from pathlib import Path

from app.staff.model import (
    StaffAttendance,
    StaffMember,
    StaffProfession,
    StaffSession,
)


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0014_staff_domain.py"
)
ALEMBIC_ENV = MIGRATION.parents[1] / "env.py"


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("staff_domain_migration", MIGRATION)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_staff_models_have_owner_boundaries_and_hot_path_indexes():
    assert StaffMember.__tablename__ == "staff_members"
    assert StaffProfession.__tablename__ == "staff_professions"
    assert StaffAttendance.__tablename__ == "staff_attendance"
    assert StaffSession.__tablename__ == "staff_sessions"

    member_indexes = {index.name: index for index in StaffMember.__table__.indexes}
    profession_indexes = {
        index.name: index for index in StaffProfession.__table__.indexes
    }
    attendance_indexes = {
        index.name: index for index in StaffAttendance.__table__.indexes
    }
    session_indexes = {index.name: index for index in StaffSession.__table__.indexes}

    assert member_indexes["uq_staff_members_business_legacy"].unique is True
    assert member_indexes["uq_staff_members_business_login"].unique is True
    assert "ix_staff_members_business_status_name" in member_indexes
    assert profession_indexes["uq_staff_professions_business_name"].unique is True
    assert attendance_indexes["uq_staff_attendance_staff_date"].unique is True
    assert "ix_staff_attendance_business_date" in attendance_indexes
    assert session_indexes["uq_staff_sessions_token_hash"].unique is True
    assert "ix_staff_sessions_active_staff" in session_indexes

    assert StaffMember.__table__.c.business_account_id.foreign_keys
    assert StaffAttendance.__table__.c.staff_id.foreign_keys
    assert StaffSession.__table__.c.staff_id.foreign_keys


def test_staff_migration_backfills_real_v1656_rows_idempotently_and_safely():
    source = MIGRATION.read_text(encoding="utf-8")
    upper = source.upper()

    assert 'revision = "0014_staff_domain"' in source
    assert 'down_revision = "0013_queue_provider_backfill"' in source
    for table in (
        "staff_members",
        "staff_professions",
        "staff_attendance",
        "staff_sessions",
    ):
        assert f'"{table}"' in source

    assert "cabinet_resources" in source
    assert "cabinet_records" in source
    assert "cabinet_record_fields" in source
    assert "business_profiles" in source
    assert "cabinet_payload" in source
    assert "staff_attendance" in source
    assert "staff_professions" in source
    assert "ON CONFLICT" in upper
    assert "DO UPDATE" in upper
    assert "queue_providers" in source
    assert "legacy_staff_id" in source
    assert "QUEUE_STAFF_RESTORE_SQL" in source
    assert "op.execute(QUEUE_STAFF_RESTORE_SQL)" in source

    # Eski ochiq parol va sessiya tokenlari yangi domenga ko'chirilmaydi.
    assert "pass_plain" not in source
    assert "INSERT INTO staff_sessions" not in source
    assert "password_hash" in source
    assert "NULL::varchar" in source or "NULL" in source


def test_staff_backfill_statements_are_complete_postgresql_ctes():
    migration = _load_migration_module()

    for statement in (
        migration.STAFF_BACKFILL_SQL,
        migration.PROFESSION_BACKFILL_SQL,
        migration.ATTENDANCE_BACKFILL_SQL,
    ):
        assert statement.lstrip().startswith("WITH\n")

    assert "{{" not in migration.STAFF_BACKFILL_SQL
    assert "^[a-z][a-z0-9_]{2,19}$" in migration.STAFF_BACKFILL_SQL


def test_staff_migration_is_reversible_without_touching_other_systemization_data():
    source = MIGRATION.read_text(encoding="utf-8")
    lowered = source.casefold()
    downgrade = source[source.index("def downgrade() -> None:") :]

    for forbidden in ("insert into sales", "insert into expenses", "insert into debtors"):
        assert forbidden not in lowered
    assert downgrade.index('drop_table("staff_sessions")') < downgrade.index(
        'drop_table("staff_members")'
    )
    assert downgrade.index('drop_table("staff_attendance")') < downgrade.index(
        'drop_table("staff_members")'
    )


def test_alembic_metadata_registers_staff_models():
    source = ALEMBIC_ENV.read_text(encoding="utf-8")
    assert "from app.staff import model as staff_model" in source
