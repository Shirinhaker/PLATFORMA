from datetime import UTC, datetime
import sqlite3

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.db.base import Base
from app.legacy_migration.model import (
    LegacyIdMap,
    MigrationEnvironment,
    MigrationIssue,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
)
from app.legacy_migration.reconcile import (
    reconcile_accounts,
    reconcile_businesses,
)
from app.profiles.model import BusinessProfile, UserProfile


NOW = datetime(2026, 7, 29, 0, 0, tzinfo=UTC)


class AsyncSessionAdapter:
    def __init__(self, session: Session):
        self.sync = session
        self.sequences: dict[str, int] = {}

    def add(self, item):
        self.sync.add(item)

    async def flush(self):
        for item in list(self.sync.new):
            if not hasattr(item, "id") or getattr(item, "id") is not None:
                continue
            table = item.__table__.name
            if table not in self.sequences:
                column = item.__table__.c.id
                current = self.sync.scalar(select(func.max(column))) or 0
                self.sequences[table] = int(current)
            self.sequences[table] += 1
            item.id = self.sequences[table]
        self.sync.flush()

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def get(self, model, key, **kwargs):
        return self.sync.get(model, key)


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            MigrationRun.__table__,
            Account.__table__,
            UserProfile.__table__,
            BusinessProfile.__table__,
            LegacyIdMap.__table__,
            MigrationIssue.__table__,
        ),
    )
    session = Session(engine, expire_on_commit=False)
    run = MigrationRun(
        id=1,
        source_database_sha256="a" * 64,
        media_manifest_sha256="b" * 64,
        schema_version="0003_phase3c_content",
        environment=MigrationEnvironment.STAGING,
        stage=MigrationStage.ACCOUNTS,
        status=MigrationStatus.RUNNING,
        counters_json={},
        error_count=0,
        started_at=NOW,
    )
    session.add(run)
    session.commit()
    try:
        yield AsyncSessionAdapter(session), run
    finally:
        session.close()
        engine.dispose()


def legacy_source(
    users: list[dict[str, object]],
    businesses: list[dict[str, object]] | None = None,
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
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
            avatar_file TEXT,
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
            telegram TEXT,
            work_hours TEXT,
            address TEXT,
            lat REAL,
            lng REAL,
            logo_file TEXT,
            logo_x REAL,
            logo_y REAL,
            logo_zoom REAL,
            biz_login TEXT,
            biz_pass_hash TEXT,
            status TEXT,
            username TEXT,
            pay_card TEXT,
            pay_holder TEXT,
            pay_qr TEXT,
            director TEXT,
            inn TEXT,
            created_at INTEGER
        );
        """
    )
    user_defaults = {
        "tg_id": None,
        "username": "",
        "login": "",
        "pass_hash": "",
        "role": "user",
        "name": "",
        "phone": "",
        "region": "",
        "district": "",
        "mahalla": "",
        "lat": None,
        "lng": None,
        "location_exact": 0,
        "avatar_file": "",
        "avatar_x": 50.0,
        "avatar_y": 50.0,
        "avatar_zoom": 1.0,
        "status": "active",
        "created_at": 1_722_211_200,
    }
    for supplied in users:
        row = user_defaults | supplied
        connection.execute(
            """
            INSERT INTO users (
                id, tg_id, username, login, pass_hash, role, name, phone,
                region, district, mahalla, lat, lng, location_exact,
                avatar_file, avatar_x, avatar_y, avatar_zoom, status, created_at
            ) VALUES (
                :id, :tg_id, :username, :login, :pass_hash, :role, :name,
                :phone, :region, :district, :mahalla, :lat, :lng,
                :location_exact, :avatar_file, :avatar_x, :avatar_y,
                :avatar_zoom, :status, :created_at
            )
            """,
            row,
        )
    business_defaults = {
        "name": "",
        "yon": "",
        "tur": "",
        "descr": "",
        "phone": "",
        "telegram": "",
        "work_hours": "",
        "address": "",
        "lat": None,
        "lng": None,
        "logo_file": "",
        "logo_x": 50.0,
        "logo_y": 50.0,
        "logo_zoom": 1.0,
        "biz_login": "",
        "biz_pass_hash": "",
        "status": "active",
        "username": "",
        "pay_card": "",
        "pay_holder": "",
        "pay_qr": "",
        "director": "",
        "inn": "",
        "created_at": 1_722_211_200,
    }
    for supplied in businesses or []:
        row = business_defaults | supplied
        columns = ", ".join(row)
        placeholders = ", ".join(f":{key}" for key in row)
        connection.execute(
            f"INSERT INTO businesses ({columns}) VALUES ({placeholders})",
            row,
        )
    connection.commit()
    return connection


def seed_account(
    store: AsyncSessionAdapter,
    *,
    account_id: int,
    account_type: AccountType,
    login: str,
    telegram_user_id: int | None,
) -> Account:
    account = Account(
        id=account_id,
        account_type=account_type,
        login=login,
        password_hash="existing",
        telegram_user_id=telegram_user_id,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )
    store.sync.add(account)
    store.sync.commit()
    return account


async def mapping(
    store: AsyncSessionAdapter,
    entity_type: str,
    legacy_id: int,
) -> LegacyIdMap:
    return (
        await store.scalars(
            select(LegacyIdMap).where(
                LegacyIdMap.entity_type == entity_type,
                LegacyIdMap.legacy_id == legacy_id,
            )
        )
    ).one()


async def issue_codes(store: AsyncSessionAdapter) -> list[str]:
    return list(
        await store.scalars(
            select(MigrationIssue.issue_code).order_by(MigrationIssue.id)
        )
    )


@pytest.mark.asyncio
async def test_existing_business_is_reused_while_user_account_is_created(store):
    db, run = store
    existing = seed_account(
        db,
        account_id=41,
        account_type=AccountType.BUSINESS,
        login="turon",
        telegram_user_id=9001,
    )
    source = legacy_source(
        [
            {
                "id": 7,
                "role": "business",
                "login": "owner-key",
                "tg_id": 9001,
                "name": "Turon",
            }
        ],
        [
            {
                "id": 3,
                "user_id": 7,
                "name": "Turon Savdo",
                "biz_login": " Turon ",
                "biz_pass_hash": "legacy-hash",
            }
        ],
    )

    accounts = await reconcile_accounts(db, source, run)
    businesses = await reconcile_businesses(db, source, run)
    user_link = await mapping(db, "user_account", 7)
    business_link = await mapping(db, "business_account", 3)

    assert user_link.target_id != existing.id
    assert business_link.target_id == existing.id
    assert accounts.created == 1
    assert businesses.created == 1
    assert existing.password_hash == "legacy-hash"


@pytest.mark.asyncio
async def test_exact_telegram_and_type_are_reused_when_login_differs(store):
    db, run = store
    existing = seed_account(
        db,
        account_id=42,
        account_type=AccountType.USER,
        login="u_existing",
        telegram_user_id=7001,
    )
    source = legacy_source(
        [
            {
                "id": 8,
                "login": "u_old",
                "pass_hash": "legacy-hash",
                "tg_id": 7001,
                "name": "Ali",
            }
        ]
    )

    result = await reconcile_accounts(db, source, run)

    assert (await mapping(db, "user_account", 8)).target_id == existing.id
    assert result.updated == 1
    assert existing.login == "u_old"
    assert existing.password_hash == "legacy-hash"


@pytest.mark.asyncio
async def test_duplicate_telegram_id_is_not_merged(store):
    db, run = store
    source = legacy_source(
        [
            {"id": 1, "login": "u_one", "tg_id": 55, "name": "One"},
            {"id": 2, "login": "u_two", "tg_id": 55, "name": "Two"},
        ]
    )

    result = await reconcile_accounts(db, source, run)
    targets = list(
        await db.scalars(
            select(LegacyIdMap.target_id).where(
                LegacyIdMap.entity_type == "user_account"
            )
        )
    )

    assert result.quarantined == 2
    assert (await issue_codes(db)).count("identity.telegram_duplicate") == 2
    assert targets == [None, None]


@pytest.mark.asyncio
async def test_duplicate_phone_is_not_merged(store):
    db, run = store
    source = legacy_source(
        [
            {"id": 1, "login": "u_one", "phone": "+99890 123-45-67"},
            {"id": 2, "login": "u_two", "phone": "+998901234567"},
        ]
    )

    result = await reconcile_accounts(db, source, run)

    assert result.quarantined == 2
    assert (await issue_codes(db)).count("identity.phone_duplicate") == 2


@pytest.mark.asyncio
async def test_mismatched_account_type_is_quarantined(store):
    db, run = store
    seed_account(
        db,
        account_id=50,
        account_type=AccountType.BUSINESS,
        login="shared_login",
        telegram_user_id=None,
    )
    source = legacy_source(
        [{"id": 5, "role": "user", "login": "shared_login"}]
    )

    result = await reconcile_accounts(db, source, run)

    assert result.quarantined == 1
    assert "identity.account_type_mismatch" in await issue_codes(db)


@pytest.mark.asyncio
async def test_new_account_is_created_once_with_user_profile(store):
    db, run = store
    source = legacy_source(
        [
            {
                "id": 9,
                "login": " U_New ",
                "pass_hash": "legacy-hash",
                "name": "Yangi foydalanuvchi",
                "district": "Qumqo‘rg‘on",
            }
        ]
    )

    first = await reconcile_accounts(db, source, run)
    second = await reconcile_accounts(db, source, run)
    linked = await mapping(db, "user_account", 9)
    account = await db.get(Account, linked.target_id)
    profile = await db.get(UserProfile, linked.target_id)

    assert first.created == 1
    assert second.created == 0
    assert second.reused == 1
    assert account.login == "u_new"
    assert account.password_hash == "legacy-hash"
    assert profile.name == "Yangi foydalanuvchi"
    assert profile.district == "Qumqo‘rg‘on"


@pytest.mark.asyncio
async def test_taken_user_public_username_does_not_block_account_migration(
    store,
):
    db, run = store
    existing = seed_account(
        db,
        account_id=201,
        account_type=AccountType.USER,
        login="existing_user",
        telegram_user_id=9201,
    )
    db.sync.add(
        UserProfile(
            account_id=existing.id,
            name="Mavjud profil",
            phone="",
            public_username="Choriyeva73",
            region="",
            district="",
            mahalla="",
            latitude=None,
            longitude=None,
            location_exact=False,
            avatar_object_key="",
            avatar_x=50.0,
            avatar_y=50.0,
            avatar_zoom=1.0,
        )
    )
    db.sync.commit()
    source = legacy_source(
        [
            {
                "id": 41,
                "login": "incoming_user",
                "tg_id": 9202,
                "username": "choriyeva73",
                "name": "Muhabbat",
            }
        ]
    )

    result = await reconcile_accounts(db, source, run)
    rerun = await reconcile_accounts(db, source, run)
    linked = await mapping(db, "user_account", 41)
    migrated = await db.get(UserProfile, linked.target_id)

    assert result.created == 1
    assert result.quarantined == 0
    assert result.issues == 1
    assert rerun.created == 0
    assert rerun.reused == 1
    assert rerun.issues == 0
    assert linked.target_id != existing.id
    assert migrated.name == "Muhabbat"
    assert migrated.public_username == ""
    assert (
        await db.get(UserProfile, existing.id)
    ).public_username == "Choriyeva73"
    assert "profile.public_username_conflict" in await issue_codes(db)
    assert (
        await db.scalar(select(func.count()).select_from(Account))
    ) == 2
    assert (
        await db.scalar(select(func.count()).select_from(UserProfile))
    ) == 2
    assert (
        await db.scalar(select(func.count()).select_from(MigrationIssue))
    ) == 1


@pytest.mark.asyncio
async def test_business_profile_is_linked_to_separate_business_account(store):
    db, run = store
    source = legacy_source(
        [{"id": 7, "role": "business", "login": "owner-key", "name": "Owner"}],
        [
            {
                "id": 3,
                "user_id": 7,
                "name": "Turon Savdo",
                "yon": "Savdo",
                "tur": "Mebel",
                "biz_login": "b_turon",
                "biz_pass_hash": "legacy-business-hash",
                "work_hours": '{"monday":["09:00","18:00"]}',
            }
        ],
    )

    accounts = await reconcile_accounts(db, source, run)
    businesses = await reconcile_businesses(db, source, run)
    owner = await mapping(db, "user_account", 7)
    business = await mapping(db, "business_account", 3)
    profile = await db.get(BusinessProfile, business.target_id)

    assert accounts.created == 1
    assert businesses.created == 1
    assert business.target_id != owner.target_id
    assert profile.name == "Turon Savdo"
    assert profile.direction == "Savdo"
    assert profile.activity_type == "Mebel"
    assert profile.work_hours == {"monday": ["09:00", "18:00"]}
    assert (
        await db.scalar(select(func.count()).select_from(Account))
    ) == 2


@pytest.mark.asyncio
async def test_taken_business_public_username_does_not_block_migration(
    store,
):
    db, run = store
    existing = seed_account(
        db,
        account_id=301,
        account_type=AccountType.BUSINESS,
        login="existing_business",
        telegram_user_id=9301,
    )
    db.sync.add(
        BusinessProfile(
            account_id=existing.id,
            name="Mavjud biznes",
            phone="",
            description="",
            public_username="Turon_Savdo",
            direction="",
            activity_type="",
            address="",
            latitude=None,
            longitude=None,
            work_hours={},
            pay_card="",
            pay_holder="",
            pay_qr_object_key="",
            director="",
            tax_id="",
            logo_object_key="",
            logo_x=50.0,
            logo_y=50.0,
            logo_zoom=1.0,
        )
    )
    db.sync.commit()
    source = legacy_source(
        [
            {
                "id": 51,
                "login": "incoming_owner",
                "tg_id": 9302,
            }
        ],
        [
            {
                "id": 61,
                "user_id": 51,
                "name": "Yangi Turon",
                "biz_login": "incoming_business",
                "username": "turon_savdo",
            }
        ],
    )
    await reconcile_accounts(db, source, run)

    result = await reconcile_businesses(db, source, run)
    rerun = await reconcile_businesses(db, source, run)
    linked = await mapping(db, "business_account", 61)
    migrated = await db.get(BusinessProfile, linked.target_id)

    assert result.created == 1
    assert result.quarantined == 0
    assert result.issues == 1
    assert rerun.created == 0
    assert rerun.reused == 1
    assert rerun.issues == 0
    assert linked.target_id != existing.id
    assert migrated.name == "Yangi Turon"
    assert migrated.public_username == ""
    assert (
        await db.get(BusinessProfile, existing.id)
    ).public_username == "Turon_Savdo"
    assert "profile.public_username_conflict" in await issue_codes(db)
    assert (
        await db.scalar(select(func.count()).select_from(Account))
    ) == 3
    assert (
        await db.scalar(select(func.count()).select_from(BusinessProfile))
    ) == 2
    assert (
        await db.scalar(select(func.count()).select_from(MigrationIssue))
    ) == 1


@pytest.mark.asyncio
async def test_business_with_missing_owner_is_quarantined(store):
    db, run = store
    source = legacy_source(
        [],
        [{"id": 4, "user_id": 999, "name": "Bog‘lanmagan biznes"}],
    )

    result = await reconcile_businesses(db, source, run)

    assert result.quarantined == 1
    assert (await mapping(db, "business_account", 4)).target_id is None
    assert "identity.business_owner_unresolved" in await issue_codes(db)


@pytest.mark.asyncio
async def test_business_owner_migrates_separate_user_and_business_accounts(
    store,
):
    db, run = store
    source = legacy_source(
        [
            {
                "id": 17,
                "role": "business",
                "login": "u_owner",
                "pass_hash": "user-hash",
                "tg_id": 9017,
                "name": "Oddiy profil",
            }
        ],
        [
            {
                "id": 23,
                "user_id": 17,
                "name": "Biznes profil",
                "biz_login": "b_owner",
                "biz_pass_hash": "business-hash",
            }
        ],
    )

    accounts = await reconcile_accounts(db, source, run)
    businesses = await reconcile_businesses(db, source, run)
    user_mapping = await mapping(db, "user_account", 17)
    business_mapping = await mapping(db, "business_account", 23)
    user_account = await db.get(Account, user_mapping.target_id)
    business_account = await db.get(Account, business_mapping.target_id)

    assert accounts.created == 1
    assert businesses.created == 1
    assert user_mapping.target_id != business_mapping.target_id
    assert user_account.account_type is AccountType.USER
    assert user_account.login == "u_owner"
    assert user_account.password_hash == "user-hash"
    assert business_account.account_type is AccountType.BUSINESS
    assert business_account.login == "b_owner"
    assert business_account.password_hash == "business-hash"
    assert await db.get(UserProfile, user_account.id) is not None
    assert await db.get(BusinessProfile, business_account.id) is not None


@pytest.mark.asyncio
async def test_rerun_splits_user_mapping_from_existing_business_account(store):
    db, run = store
    existing_business = seed_account(
        db,
        account_id=71,
        account_type=AccountType.BUSINESS,
        login="b_owner",
        telegram_user_id=9071,
    )
    db.sync.add_all(
        [
            LegacyIdMap(
                id=101,
                entity_type="user_account",
                legacy_id=17,
                target_id=existing_business.id,
                source_row_hash="old-user-hash",
                mapping_status="mapped",
                review_reason="",
                last_run_id=run.id,
            ),
            LegacyIdMap(
                id=102,
                entity_type="business_account",
                legacy_id=23,
                target_id=existing_business.id,
                source_row_hash="old-business-hash",
                mapping_status="mapped",
                review_reason="",
                last_run_id=run.id,
            ),
        ]
    )
    db.sync.commit()
    source = legacy_source(
        [
            {
                "id": 17,
                "role": "business",
                "login": "u_owner",
                "pass_hash": "user-hash",
                "tg_id": 9071,
                "name": "Oddiy profil",
            }
        ],
        [
            {
                "id": 23,
                "user_id": 17,
                "name": "Biznes profil",
                "biz_login": "b_owner",
                "biz_pass_hash": "business-hash",
            }
        ],
    )

    result = await reconcile_accounts(db, source, run)
    user_mapping = await mapping(db, "user_account", 17)
    business_mapping = await mapping(db, "business_account", 23)
    user_account = await db.get(Account, user_mapping.target_id)

    assert result.created == 1
    assert user_mapping.target_id != existing_business.id
    assert business_mapping.target_id == existing_business.id
    assert user_account.account_type is AccountType.USER
    assert user_account.login == "u_owner"
    assert existing_business.account_type is AccountType.BUSINESS
    assert existing_business.login == "b_owner"


@pytest.mark.asyncio
async def test_existing_user_account_restores_legacy_login_and_password(store):
    db, run = store
    existing = seed_account(
        db,
        account_id=81,
        account_type=AccountType.USER,
        login="u_generated",
        telegram_user_id=9081,
    )
    source = legacy_source(
        [
            {
                "id": 18,
                "login": "u_original",
                "pass_hash": "original-user-hash",
                "tg_id": 9081,
                "name": "Haqiqiy oddiy profil",
            }
        ]
    )

    result = await reconcile_accounts(db, source, run)
    linked = await mapping(db, "user_account", 18)

    assert result.created == 0
    assert result.updated == 1
    assert linked.target_id == existing.id
    assert existing.login == "u_original"
    assert existing.password_hash == "original-user-hash"


@pytest.mark.asyncio
async def test_existing_business_account_restores_legacy_credentials(store):
    db, run = store
    user_account = seed_account(
        db,
        account_id=91,
        account_type=AccountType.USER,
        login="u_owner",
        telegram_user_id=9091,
    )
    business_account = seed_account(
        db,
        account_id=92,
        account_type=AccountType.BUSINESS,
        login="b_generated",
        telegram_user_id=9091,
    )
    db.sync.add_all(
        [
            LegacyIdMap(
                id=111,
                entity_type="user_account",
                legacy_id=19,
                target_id=user_account.id,
                source_row_hash="user-row-hash",
                mapping_status="mapped",
                review_reason="",
                last_run_id=run.id,
            ),
            LegacyIdMap(
                id=112,
                entity_type="business_account",
                legacy_id=29,
                target_id=business_account.id,
                source_row_hash="business-row-hash",
                mapping_status="mapped",
                review_reason="",
                last_run_id=run.id,
            ),
        ]
    )
    db.sync.commit()
    source = legacy_source(
        [
            {
                "id": 19,
                "role": "business",
                "login": "u_owner",
                "pass_hash": "user-hash",
                "tg_id": 9091,
            }
        ],
        [
            {
                "id": 29,
                "user_id": 19,
                "name": "Haqiqiy biznes",
                "biz_login": "b_original",
                "biz_pass_hash": "original-business-hash",
            }
        ],
    )

    await reconcile_businesses(db, source, run)
    linked = await mapping(db, "business_account", 29)

    assert linked.target_id == business_account.id
    assert business_account.login == "b_original"
    assert business_account.password_hash == "original-business-hash"
    assert (
        await db.scalar(select(func.count()).select_from(Account))
    ) == 2


@pytest.mark.asyncio
async def test_empty_legacy_password_does_not_erase_working_password(store):
    db, run = store
    existing = seed_account(
        db,
        account_id=101,
        account_type=AccountType.USER,
        login="u_generated",
        telegram_user_id=9101,
    )
    source = legacy_source(
        [
            {
                "id": 20,
                "login": "u_original",
                "pass_hash": "",
                "tg_id": 9101,
            }
        ]
    )

    await reconcile_accounts(db, source, run)

    assert existing.login == "u_original"
    assert existing.password_hash == "existing"


@pytest.mark.asyncio
async def test_mapped_user_disagreeing_with_source_identity_is_quarantined(
    store,
):
    db, run = store
    mapped = seed_account(
        db,
        account_id=111,
        account_type=AccountType.USER,
        login="mapped_login",
        telegram_user_id=9111,
    )
    seed_account(
        db,
        account_id=112,
        account_type=AccountType.USER,
        login="source_login",
        telegram_user_id=None,
    )
    db.sync.add(
        LegacyIdMap(
            id=121,
            entity_type="user_account",
            legacy_id=21,
            target_id=mapped.id,
            source_row_hash="old-row-hash",
            mapping_status="mapped",
            review_reason="",
            last_run_id=run.id,
        )
    )
    db.sync.commit()
    source = legacy_source(
        [
            {
                "id": 21,
                "login": "source_login",
                "pass_hash": "source-hash",
                "tg_id": 9111,
            }
        ]
    )

    result = await reconcile_accounts(db, source, run)
    linked = await mapping(db, "user_account", 21)

    assert result.quarantined == 1
    assert linked.target_id is None
    assert linked.review_reason == "identity.identifiers_disagree"
    assert mapped.login == "mapped_login"
    assert "identity.identifiers_disagree" in await issue_codes(db)


@pytest.mark.asyncio
async def test_duplicate_business_login_is_quarantined_before_mutation(store):
    db, run = store
    source = legacy_source(
        [
            {
                "id": 31,
                "login": "u_one",
                "tg_id": 9131,
                "username": "u_one_public",
            },
            {
                "id": 32,
                "login": "u_two",
                "tg_id": 9132,
                "username": "u_two_public",
            },
        ],
        [
            {
                "id": 41,
                "user_id": 31,
                "name": "Birinchi biznes",
                "biz_login": "same_business",
                "biz_pass_hash": "first-hash",
            },
            {
                "id": 42,
                "user_id": 32,
                "name": "Ikkinchi biznes",
                "biz_login": "same_business",
                "biz_pass_hash": "second-hash",
            },
        ],
    )
    await reconcile_accounts(db, source, run)

    result = await reconcile_businesses(db, source, run)
    targets = list(
        await db.scalars(
            select(LegacyIdMap.target_id)
            .where(LegacyIdMap.entity_type == "business_account")
            .order_by(LegacyIdMap.legacy_id)
        )
    )

    assert result.quarantined == 2
    assert targets == [None, None]
    assert (await issue_codes(db)).count("identity.login_duplicate") == 2
    assert (
        await db.scalar(
            select(func.count())
            .select_from(Account)
            .where(Account.account_type == AccountType.BUSINESS)
        )
    ) == 0
