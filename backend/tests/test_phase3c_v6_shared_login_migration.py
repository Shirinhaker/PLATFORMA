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
from app.legacy_migration.profile_parity_v7 import (
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
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY, order_id INTEGER, item_name TEXT,
            qty INTEGER, line_total INTEGER, pass_hash TEXT
        );
        CREATE TABLE order_messages (
            id INTEGER PRIMARY KEY, order_id INTEGER, text TEXT,
            is_deleted INTEGER, created_at INTEGER, secret TEXT
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
        CREATE TABLE listings (
            id INTEGER PRIMARY KEY, user_id INTEGER, business_id INTEGER,
            title TEXT, status TEXT, is_demo INTEGER
        );
        CREATE TABLE listing_media (
            id INTEGER PRIMARY KEY, listing_id INTEGER, mtype TEXT,
            tg_file_id TEXT, pos INTEGER, is_demo INTEGER
        );
        CREATE TABLE stories (
            id INTEGER PRIMARY KEY, owner_type TEXT, owner_id INTEGER,
            caption TEXT, status TEXT, is_demo INTEGER
        );
        CREATE TABLE payment_requests (
            id INTEGER PRIMARY KEY, actor_type TEXT, user_id INTEGER,
            business_id INTEGER, status TEXT, amount_snapshot INTEGER,
            is_demo INTEGER
        );
        CREATE TABLE payment_attempts (
            id INTEGER PRIMARY KEY, payment_request_id INTEGER,
            attempt_no INTEGER, review_status TEXT, secret TEXT
        );
        CREATE TABLE payment_events (
            id INTEGER PRIMARY KEY, payment_request_id INTEGER,
            from_status TEXT, to_status TEXT, created_at INTEGER
        );
        CREATE TABLE staff (
            id INTEGER PRIMARY KEY, business_id INTEGER, name TEXT,
            pass_hash TEXT, is_demo INTEGER
        );
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY, business_id INTEGER, title TEXT,
            status TEXT, is_demo INTEGER
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
            (
                46, "user", 5, "business", 4, "product", "Muhr", "new",
                350000, 1722211200, 1722211200, 0,
            ),
            (
                47, "user", 9, "business", 4, "service", "Dizayn",
                "accepted", 15000, 1722211300, 1722211300, 0,
            ),
        ],
    )
    source.executemany(
        "INSERT INTO order_items VALUES (?,?,?,?,?,?)",
        [
            (1, 46, "Muhr", 2, 350000, "must-not-leak"),
            (2, 47, "Dizayn", 1, 15000, "must-not-leak"),
        ],
    )
    source.execute(
        "INSERT INTO order_messages VALUES (1,46,'Tayyor bo‘ldimi?',0,1722211210,'must-not-leak')"
    )
    source.execute("INSERT INTO saved VALUES (1,5,'business',4,1722211200)")
    source.execute(
        "INSERT INTO notifications VALUES (1,5,'user',5,'Yangi xabar',0,1722211200)"
    )
    source.executemany(
        "INSERT INTO follows VALUES (?,?,?,?,?)",
        [
            (1, 5, "business", 4, 1722211200),
            (2, 9, "user", 5, 1722211200),
            (3, 8, "business", 4, 1722211200),
        ],
    )
    source.execute(
        "INSERT INTO specialists VALUES (1,5,'Dizayner','Tajriba','100000','Qumqo‘rg‘on',1,1)"
    )
    source.execute("INSERT INTO items VALUES (1,4,'Muhr','15000',1,2,1)")
    source.execute("INSERT INTO debtors VALUES (1,4,'Vali',100000)")
    source.execute("INSERT INTO business_follows VALUES (1,4,'business',8)")
    source.executemany(
        "INSERT INTO listings VALUES (?,?,?,?,?,?)",
        [
            (3, 5, None, "Uy sotiladi", "active", 0),
            (4, 5, 4, "Biznes e’loni", "active", 0),
            (5, 5, 4, "Demo e’lon", "active", 1),
        ],
    )
    source.executemany(
        "INSERT INTO listing_media VALUES (?,?,?,?,?,?)",
        [
            (1, 3, "photo", "real-photo", 0, 0),
            (2, 5, "photo", "demo-photo", 0, 1),
        ],
    )
    source.executemany(
        "INSERT INTO stories VALUES (?,?,?,?,?,?)",
        [
            (1, "user", 5, "Haqiqiy user istoriya", "active", 0),
            (2, "business", 4, "Haqiqiy biznes istoriya", "active", 0),
            (3, "business", 4, "Demo istoriya", "active", 1),
        ],
    )
    source.executemany(
        "INSERT INTO payment_requests VALUES (?,?,?,?,?,?,?)",
        [
            (1, "user", 5, None, "approved", 10000, 0),
            (2, "business", 5, 4, "approved", 149000, 0),
            (3, "business", 5, 4, "approved", 99000, 1),
        ],
    )
    source.executemany(
        "INSERT INTO payment_attempts VALUES (?,?,?,?,?)",
        [
            (1, 1, 1, "approved", "must-not-leak"),
            (2, 2, 1, "approved", "must-not-leak"),
        ],
    )
    source.executemany(
        "INSERT INTO payment_events VALUES (?,?,?,?,?)",
        [
            (1, 1, "pending", "approved", 1722211220),
            (2, 2, "pending", "approved", 1722211230),
        ],
    )
    source.executemany(
        "INSERT INTO staff VALUES (?,?,?,?,?)",
        [
            (1, 4, "Haqiqiy xodim", "must-not-leak", 0),
            (2, 4, "Demo xodim", "must-not-leak", 1),
        ],
    )
    source.execute(
        "INSERT INTO documents VALUES (1,4,'Shartnoma','active',0)"
    )
    source.commit()
    return source


async def test_complete_cabinet_migration_preserves_only_real_data(db_session):
    old_run = MigrationRun(
        source_database_sha256="a" * 64,
        media_manifest_sha256="b" * 64,
        schema_version="0005_phase3c_profile_cabinet_parity_v1",
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
        schema_version="0006_phase3c_complete_cabinet_v1",
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
    user_payload = user_profile.cabinet_payload
    assert user_payload["orders"][0]["title"] == "Muhr"
    assert user_payload["orders"][0]["items"][0]["item_name"] == "Muhr"
    assert "pass_hash" not in user_payload["orders"][0]["items"][0]
    assert "secret" not in user_payload["orders"][0]["messages"][0]
    assert [row["title"] for row in user_payload["listings"]] == [
        "Uy sotiladi"
    ]
    assert user_payload["listings"][0]["media"][0]["tg_file_id"] == "real-photo"
    assert [row["caption"] for row in user_payload["stories"]] == [
        "Haqiqiy user istoriya"
    ]
    assert len(user_payload["payments"]) == 1
    assert "secret" not in user_payload["payments"][0]["attempts"][0]

    assert business_profile.followers_count == 2
    assert business_profile.following_count == 1
    assert business_profile.rating_sum == 18
    assert business_profile.rating_count == 5
    assert business_profile.map_visible is True
    assert business_profile.dashboard_snapshot["new_orders"] == 1
    assert business_profile.dashboard_snapshot["low_stock"] == 1
    assert business_profile.dashboard_snapshot["debt_total"] == 100000
    business_payload = business_profile.cabinet_payload
    assert len(business_payload["orders"]) == 2
    assert business_payload["orders"][0]["items"][0]["item_name"] == "Muhr"
    assert business_payload["items"][0]["name"] == "Muhr"
    assert [row["title"] for row in business_payload["listings"]] == [
        "Biznes e’loni"
    ]
    assert [row["caption"] for row in business_payload["stories"]] == [
        "Haqiqiy biznes istoriya"
    ]
    assert len(business_payload["payment_requests"]) == 1
    assert len(business_payload["subscription_payments"]) == 1
    assert [row["name"] for row in business_payload["staff"]] == [
        "Haqiqiy xodim"
    ]
    assert "pass_hash" not in business_payload["staff"][0]
    assert [row["title"] for row in business_payload["documents"]] == [
        "Shartnoma"
    ]
