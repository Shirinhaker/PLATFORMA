from datetime import UTC, datetime
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.accounts.model import Account, AccountType
from app.auth.model import AuthChallenge, AuthSession, PendingRegistration
from app.profiles.model import BusinessProfile, UserProfile


def load_phase2_migration() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0002_auth_profiles.py"
    )
    spec = importlib.util.spec_from_file_location("phase2_migration", path)
    if spec is None or spec.loader is None:
        raise AssertionError("Phase 2 migration yuklanmadi.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_identity_models_use_separate_account_types():
    assert AccountType.USER.value == "user"
    assert AccountType.BUSINESS.value == "business"
    assert UserProfile.__table__.c.account_id.primary_key
    assert BusinessProfile.__table__.c.account_id.primary_key
    assert AuthChallenge.__table__.c.pending_registration_id.nullable
    assert AuthSession.__table__.c.token_hash.unique
    assert PendingRegistration.__table__.c.payload_json.nullable is False


def test_phase2_migration_creates_only_additive_identity_tables():
    class RecordingOperations:
        def __init__(self):
            self.created_tables: list[str] = []
            self.created_indexes: list[tuple[str, str]] = []

        def create_table(self, name, *columns, **kwargs):
            self.created_tables.append(name)

        def create_index(self, name, table_name, *args, **kwargs):
            self.created_indexes.append((name, table_name))

        def execute(self, *args, **kwargs):
            pass

    migration = load_phase2_migration()
    operations = RecordingOperations()
    migration.op = operations

    migration.upgrade()

    assert migration.down_revision == "0001_foundation"
    assert operations.created_tables == [
        "accounts",
        "pending_registrations",
        "auth_challenges",
        "auth_sessions",
        "user_profiles",
        "business_profiles",
    ]
    assert {table for _, table in operations.created_indexes} <= set(
        operations.created_tables
    )


async def test_one_telegram_can_own_one_account_of_each_type(db_session):
    now = datetime.now(UTC)
    db_session.add_all(
        [
            Account(
                account_type=AccountType.USER,
                login="user_one",
                password_hash="hash",
                telegram_user_id=42,
                status="active",
                created_at=now,
                updated_at=now,
            ),
            Account(
                account_type=AccountType.BUSINESS,
                login="biz_one",
                password_hash="hash",
                telegram_user_id=42,
                status="active",
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    await db_session.commit()
    rows = (await db_session.execute(select(Account))).scalars().all()
    assert {row.account_type for row in rows} == {
        AccountType.USER,
        AccountType.BUSINESS,
    }


async def test_second_account_of_same_type_for_telegram_is_rejected(db_session):
    now = datetime.now(UTC)
    db_session.add_all(
        [
            Account(
                account_type=AccountType.USER,
                login="user_one",
                password_hash="hash",
                telegram_user_id=42,
                status="active",
                created_at=now,
                updated_at=now,
            ),
            Account(
                account_type=AccountType.USER,
                login="user_two",
                password_hash="hash",
                telegram_user_id=42,
                status="active",
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
