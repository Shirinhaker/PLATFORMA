from datetime import UTC, datetime
import sqlite3

from sqlalchemy import select

from app.accounts.model import Account, AccountType
from app.legacy_migration.model import (
    LegacyIdMap,
    MigrationEnvironment,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
)
from app.legacy_migration.reconcile_v6 import (
    reconcile_accounts,
    reconcile_businesses,
)
from app.profiles.model import BusinessProfile, UserProfile


NOW = datetime(2026, 7, 30, 0, 0, tzinfo=UTC)


def source_snapshot() -> sqlite3.Connection:
    source = sqlite3.connect(":memory:")
    source.row_factory = sqlite3.Row
    source.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            tg_id INTEGER,
            username TEXT,
            login TEXT,
            pass_hash TEXT,
            role TEXT,
            name TEXT,
            phone TEXT,
            region TEXT,
            district TEXT,
            mahalla TEXT,
            lat REAL,
            lng REAL,
            location_exact INTEGER,
            avatar_x REAL,
            avatar_y REAL,
            avatar_zoom REAL,
            status TEXT,
            created_at INTEGER
        );
        CREATE TABLE businesses (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            name TEXT,
            yon TEXT,
            tur TEXT,
            descr TEXT,
            phone TEXT,
            work_hours TEXT,
            address TEXT,
            lat REAL,
            lng REAL,
            logo_x REAL,
            logo_y REAL,
            logo_zoom REAL,
            biz_login TEXT,
            biz_pass_hash TEXT,
            status TEXT,
            username TEXT,
            pay_card TEXT,
            pay_holder TEXT,
            director TEXT,
            inn TEXT,
            created_at INTEGER
        );
        """
    )
    source.execute(
        """
        INSERT INTO users VALUES (
            5, NULL, '', 'shared_owner', 'legacy-shared-hash', 'business',
            'Haqiqiy oddiy profil', '+998900000000', 'Surxondaryo',
            'Qumqo‘rg‘on', '', NULL, NULL, 0, 50, 50, 1, 'active',
            1722211200
        )
        """
    )
    source.execute(
        """
        INSERT INTO businesses VALUES (
            4, 5, 'Haqiqiy biznes', 'Savdo', 'Do‘kon', 'Tavsif',
            '+998900000000', '{}', 'Qumqo‘rg‘on', NULL, NULL, 50, 50, 1,
            '', '', 'active', '', '', '', '', '', 1722211200
        )
        """
    )
    source.commit()
    return source


async def test_v6_preserves_real_pair_without_telegram_or_business_login(
    db_session,
):
    old_run = MigrationRun(
        source_database_sha256="a" * 64,
        media_manifest_sha256="b" * 64,
        schema_version="0003_phase3c_dual_accounts_v4",
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.VERIFY,
        status=MigrationStatus.FAILED,
        counters_json={},
        error_count=0,
        started_at=NOW,
        finished_at=NOW,
    )
    db_session.add(old_run)
    await db_session.flush()

    occupied_business = Account(
        account_type=AccountType.BUSINESS,
        login="shared_owner",
        password_hash="legacy-shared-hash",
        telegram_user_id=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )
    db_session.add(occupied_business)
    await db_session.flush()
    db_session.add(
        BusinessProfile(
            account_id=occupied_business.id,
            name="Haqiqiy biznes",
            phone="+998900000000",
            description="Tavsif",
            public_username="",
            direction="Savdo",
            activity_type="Do‘kon",
            address="Qumqo‘rg‘on",
            latitude=None,
            longitude=None,
            work_hours={},
            pay_card="",
            pay_holder="",
            pay_qr_object_key="",
            director="",
            tax_id="",
            logo_object_key="",
            logo_x=50,
            logo_y=50,
            logo_zoom=1,
        )
    )
    db_session.add_all(
        [
            LegacyIdMap(
                entity_type="user_account",
                legacy_id=5,
                target_id=None,
                source_row_hash="old-user-hash",
                mapping_status="quarantined",
                review_reason="identity.account_type_mismatch",
                last_run_id=old_run.id,
            ),
            LegacyIdMap(
                entity_type="business_account",
                legacy_id=4,
                target_id=None,
                source_row_hash="old-business-hash",
                mapping_status="quarantined",
                review_reason="identity.business_owner_unresolved",
                last_run_id=old_run.id,
            ),
        ]
    )

    v6_run = MigrationRun(
        source_database_sha256="a" * 64,
        media_manifest_sha256="b" * 64,
        schema_version="0004_phase3c_shared_login_v1",
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.ACCOUNTS,
        status=MigrationStatus.RUNNING,
        counters_json={},
        error_count=0,
        started_at=NOW,
    )
    db_session.add(v6_run)
    await db_session.flush()

    source = source_snapshot()
    try:
        accounts = await reconcile_accounts(db_session, source, v6_run)
        businesses = await reconcile_businesses(db_session, source, v6_run)
        await db_session.flush()
    finally:
        source.close()

    ordinary = await db_session.scalar(
        select(Account).where(
            Account.login == "shared_owner",
            Account.account_type == AccountType.USER,
        )
    )
    business = await db_session.scalar(
        select(Account).where(
            Account.login == "shared_owner",
            Account.account_type == AccountType.BUSINESS,
        )
    )
    mappings = {
        (row.entity_type, row.legacy_id): row
        for row in (
            await db_session.scalars(
                select(LegacyIdMap).where(
                    LegacyIdMap.entity_type.in_(
                        ("user_account", "business_account")
                    )
                )
            )
        ).all()
    }

    assert accounts.quarantined == 0
    assert businesses.quarantined == 0
    assert ordinary is not None
    assert business is not None
    assert ordinary.id != business.id
    assert ordinary.password_hash == "legacy-shared-hash"
    assert business.password_hash == "legacy-shared-hash"
    assert ordinary.telegram_user_id is None
    assert business.telegram_user_id is None
    assert await db_session.get(UserProfile, ordinary.id) is not None
    assert await db_session.get(BusinessProfile, business.id) is not None
    assert mappings[("user_account", 5)].target_id == ordinary.id
    assert mappings[("user_account", 5)].mapping_status == "mapped"
    assert mappings[("business_account", 4)].target_id == business.id
    assert mappings[("business_account", 4)].mapping_status == "mapped"
    assert mappings[("user_account", 5)].last_run_id == v6_run.id
    assert mappings[("business_account", 4)].last_run_id == v6_run.id
