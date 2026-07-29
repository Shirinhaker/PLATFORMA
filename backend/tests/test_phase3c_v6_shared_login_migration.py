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
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile


NOW = datetime(2026, 7, 30, 0, 0, tzinfo=UTC)


def source_snapshot() -> sqlite3.Connection:
    source = sqlite3.connect(":memory:")
    source.row_factory = sqlite3.Row
    source.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY, tg_id INTEGER, username TEXT, login TEXT,
            pass_hash TEXT, role TEXT, name TEXT, phone TEXT, region TEXT,
            district TEXT, mahalla TEXT, lat REAL, lng REAL,
            location_exact INTEGER, avatar_x REAL, avatar_y REAL,
            avatar_zoom REAL, status TEXT, created_at INTEGER
        );
        CREATE TABLE businesses (
            id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT, yon TEXT,
            tur TEXT, descr TEXT, phone TEXT, work_hours TEXT, address TEXT,
            lat REAL, lng REAL, logo_x REAL, logo_y REAL, logo_zoom REAL,
            biz_login TEXT, biz_pass_hash TEXT, status TEXT, username TEXT,
            pay_card TEXT, pay_holder TEXT, director TEXT, inn TEXT,
            rating_sum INTEGER, rating_cnt INTEGER, map_visible INTEGER,
            created_at INTEGER
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY, customer_kind TEXT, customer_user_id INTEGER,
            provider_kind TEXT, provider_actor_id INTEGER, order_type TEXT,
            title TEXT, status TEXT, total_amount INTEGER, created_at INTEGER,
            updated_at INTEGER, problem_open INTEGER
        );
        CREATE TABLE saved (
            id INTEGER PRIMARY KEY, user_id INTEGER, target_kind TEXT,
            target_id INTEGER, created_at INTEGER
        );
        CREATE TABLE notifications (
            id INTEGER PRIMARY KEY, user_id INTEGER, actor_kind TEXT,
            actor_id INTEGER, title TEXT, is_read INTEGER, created_at INTEGER
        );
        CREATE TABLE follows (
            id INTEGER PRIMARY KEY, follower_id INTEGER, target_kind TEXT,
            target_id INTEGER, created_at INTEGER
        );
        CREATE TABLE specialists (
            id INTEGER PRIMARY KEY, user_id INTEGER, kasb TEXT, descr TEXT,
            narx TEXT, hudud TEXT, visible INTEGER, available INTEGER
        );
        CREATE TABLE items (
            id INTEGER PRIMARY KEY, business_id INTEGER, name TEXT,
            price TEXT, stock_qty REAL, min_qty REAL, track_stock INTEGER
        );
        CREATE TABLE debtors (
            id INTEGER PRIMARY KEY, business_id INTEGER, name TEXT, balance INTEGER
        );
        CREATE TABLE business_follows (
            id INTEGER PRIMARY KEY, business_id INTEGER, target_kind TEXT,
            target_id INTEGER
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
            '', '', 'active', 'haqiqiy_biznes', '', '', '', '',
            18, 5, 1, 1722211200
        )
        """
    )
    source.executemany(
        "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (46, "user", 5, "business", 4, "product", "Muhr", "new", 350000, 1722211200, 1722211200, 0),
            (47, "user", 9, "business", 4, "service", "Dizayn", "accepted", 15000, 1722211300, 1722211300, 0),
        ],
    )
    source.execute("INSERT INTO saved VALUES (1,5,'business',4,1722211200)")
    source.execute("INSERT INTO notifications VALUES (1,5,'user',5,'Yangi xabar',0,1722211200)")
    source.executemany(
        "INSERT INTO follows VALUES (?,?,?,?,?)",
        [(1,5,'business',4,1722211200), (2,9,'user',5,1722211200), (3,8,'business',4,1722211200)],
    )
    source.execute("INSERT INTO specialists VALUES (1,5,'Dizayner','Tajriba','100000','Qumqo‘rg‘on',1,1)")
    source.execute("INSERT INTO items VALUES (1,4,'Muhr','15000',1,2,1)")
    source.execute("INSERT INTO debtors VALUES (1,4,'Vali',100000)")
    source.execute("INSERT INTO business_follows VALUES (1,4,'business',8)")
    source.commit()
    return source


async def test_v6_migrates_shared_login_and_complete_profile_cabinets(db_session):
    old_run = MigrationRun(
        source_database_sha256="a" * 64,
        media_manifest_sha256="b" * 64,
        schema_version="0004_phase3c_shared_login_v1",
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.VERIFY,
        status=MigrationStatus.COMPLETED,
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

    run = MigrationRun(
        source_database_sha256="a" * 64,
        media_manifest_sha256="b" * 64,
        schema_version="0005_phase3c_profile_cabinet_parity_v1",
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.ACCOUNTS,
        status=MigrationStatus.RUNNING,
        counters_json={},
        error_count=0,
        started_at=NOW,
    )
    db_session.add(run)
    await db_session.flush()

    source = source_snapshot()
    try:
        accounts = await reconcile_accounts(db_session, source, run)
        businesses = await reconcile_businesses(db_session, source, run)
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
    assert accounts.quarantined == 0
    assert businesses.quarantined == 0
    assert ordinary is not None and business is not None
    assert ordinary.id != business.id
    assert ordinary.password_hash == business.password_hash == "legacy-shared-hash"

    user_profile = await db_session.get(UserProfile, ordinary.id)
    business_profile = await db_session.get(BusinessProfile, business.id)
    link = await db_session.get(ProfileLink, ordinary.id)
    assert user_profile is not None
    assert business_profile is not None
    assert link is not None and link.business_account_id == business.id

    assert user_profile.has_business is True
    assert user_profile.followers_count == 1
    assert user_profile.following_count == 1
    assert user_profile.dashboard_snapshot["active_orders"] == 1
    assert user_profile.dashboard_snapshot["saved"] == 1
    assert user_profile.dashboard_snapshot["unread"] == 1
    assert user_profile.specialist_profile["kasb"] == "Dizayner"
    assert user_profile.cabinet_payload["orders"][0]["title"] == "Muhr"

    assert business_profile.followers_count == 1
    assert business_profile.following_count == 1
    assert business_profile.rating_sum == 18
    assert business_profile.rating_count == 5
    assert business_profile.map_visible is True
    assert business_profile.dashboard_snapshot["new_orders"] == 1
    assert business_profile.dashboard_snapshot["low_stock"] == 1
    assert business_profile.dashboard_snapshot["debt_total"] == 100000
    assert len(business_profile.cabinet_payload["orders"]) == 2
    assert business_profile.cabinet_payload["items"][0]["name"] == "Muhr"
