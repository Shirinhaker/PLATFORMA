"""Haydovchi balansi — pul bilan bog'liq, ilgari umuman qoplanmagan.

`docs/qoplama-hisoboti.md` da bu uchta eng xavfli bo'shliqdan biri deb
belgilangan edi: `topup_driver` haydovchining pul balansini o'zgartiradi
va admin auditiga yozadi, lekin bironta test unga tegmasdi.

Bu fayl shu bo'shliqni yopadi: balans qo'shiladimi, audit yoziladimi,
yo'q haydovchida nima bo'ladi va balansni kamaytirish ishlaydimi.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.admin.moderation_model import AdminAuditLog
from app.core.errors import ApiError
from app.db.base import Base
from app.profiles.model import UserProfile
from app.taxi.model import TaxiDriver, TaxiRide
from app.taxi.service_parts import TaxiService

NOW = datetime(2026, 8, 11, 8, 0, tzinfo=UTC)
ADMIN_TG_ID = 555_001
DRIVER_ACCOUNT_ID = 2


class AsyncStore:
    def __init__(self, sync: Session):
        self.sync = sync
        self.sequences: dict[str, int] = {}

    async def get(self, model, identity, **kwargs):
        return self.sync.get(model, identity, **kwargs)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def execute(self, statement):
        return self.sync.execute(statement)

    def add(self, row):
        self.sync.add(row)

    async def flush(self):
        # SQLite `Identity()` ni avtomatik to'ldirmaydi — loyihadagi boshqa
        # testlar ham shu naqshni ishlatadi.
        for value in list(self.sync.new):
            if not hasattr(value, "id") or value.id is not None:
                continue
            table = value.__table__.name
            if table not in self.sequences:
                highest = self.sync.scalar(select(func.max(value.__table__.c.id)))
                self.sequences[table] = int(highest or 0)
            self.sequences[table] += 1
            value.id = self.sequences[table]
        self.sync.flush()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()

    def get_bind(self):
        return self.sync.get_bind()


def _account(account_id: int, name: str) -> tuple[Account, UserProfile]:
    return (
        Account(
            id=account_id,
            account_type=AccountType.USER,
            login=f"taxi-user-{account_id}",
            password_hash="hash",
            status="active",
            telegram_user_id=None,
            created_at=NOW,
            updated_at=NOW,
        ),
        UserProfile(
            account_id=account_id,
            name=name,
            phone=f"+9989000000{account_id}",
            public_username=f"taxi_{account_id}",
            region="",
            district="",
            mahalla="",
            latitude=None,
            longitude=None,
            location_exact=False,
            avatar_object_key="",
            avatar_x=50,
            avatar_y=50,
            avatar_zoom=1,
            followers_count=0,
            following_count=0,
            has_business=False,
            dashboard_snapshot={},
            recent_activity=[],
            specialist_profile={},
            cabinet_payload={},
        ),
    )


@pytest.fixture
def taxi_store():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            UserProfile.__table__,
            TaxiDriver.__table__,
            TaxiRide.__table__,
            AdminAuditLog.__table__,
        ),
    )
    sync = Session(engine, expire_on_commit=False)
    sync.add_all(_account(DRIVER_ACCOUNT_ID, "Haydovchi"))
    sync.add(
        TaxiDriver(
            id=10,
            user_account_id=DRIVER_ACCOUNT_ID,
            phone="+998901112233",
            car_model="Cobalt",
            car_plate="01 A 123 BC",
            car_color="oq",
            service="taxi",
            available=True,
            rating_sum=0,
            rating_count=0,
            balance=5_000,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    sync.commit()
    store = AsyncStore(sync)

    @asynccontextmanager
    async def sessions():
        yield store

    service = TaxiService(sessions, now_provider=lambda: NOW)
    try:
        yield service, sync
    finally:
        sync.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_topup_adds_the_amount_and_returns_the_new_balance(taxi_store):
    service, sync = taxi_store

    driver_id, balance = await service.topup_driver(
        driver_id=10,
        amount=7_500,
        admin_tg_id=ADMIN_TG_ID,
        reason="Naqd to'ldirish",
        meta={},
    )

    assert driver_id == 10
    assert balance == 12_500  # 5 000 + 7 500

    stored = sync.get(TaxiDriver, 10)
    assert stored.balance == 12_500
    # SQLite vaqt mintaqasini saqlamaydi, shuning uchun tzinfo'siz
    # solishtiramiz — bu test muhitining xususiyati, kod xatosi emas.
    assert stored.updated_at.replace(tzinfo=None) == NOW.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_topup_writes_an_audit_row_with_before_and_after(taxi_store):
    """Pul o'zgarishi izsiz qolmasligi kerak — kim, qancha, nima uchun."""
    service, sync = taxi_store

    await service.topup_driver(
        driver_id=10,
        amount=3_000,
        admin_tg_id=ADMIN_TG_ID,
        reason="Bonus",
        meta={"ip_hash": "abc", "user_agent": "test-agent"},
    )

    rows = list(sync.scalars(select(AdminAuditLog)).all())
    assert len(rows) == 1
    row = rows[0]
    assert row.admin_tg_id == ADMIN_TG_ID
    assert row.action == "taxi.driver_balance_topup"
    assert row.target_kind == "taxi_driver"
    assert row.target_id == "10"
    assert row.before_state == {"balance": 5_000}
    assert row.after_state == {"balance": 8_000, "amount": 3_000}
    assert row.reason == "Bonus"
    assert row.ip_hash == "abc"
    assert row.user_agent == "test-agent"


@pytest.mark.asyncio
async def test_topup_accepts_a_negative_amount_to_correct_a_mistake(taxi_store):
    """Admin xato to'ldirsa, uni orqaga qaytara olishi kerak."""
    service, sync = taxi_store

    _, balance = await service.topup_driver(
        driver_id=10,
        amount=-2_000,
        admin_tg_id=ADMIN_TG_ID,
        reason="Xato tuzatildi",
        meta={},
    )

    assert balance == 3_000
    assert sync.get(TaxiDriver, 10).balance == 3_000


@pytest.mark.asyncio
async def test_topup_of_a_missing_driver_is_rejected_and_writes_nothing(taxi_store):
    service, sync = taxi_store

    with pytest.raises(ApiError) as caught:
        await service.topup_driver(
            driver_id=999,
            amount=1_000,
            admin_tg_id=ADMIN_TG_ID,
            reason="Yo'q haydovchi",
            meta={},
        )

    assert caught.value.status_code == 404
    assert caught.value.code == "driver_not_found"
    # Audit jurnaliga hech narsa tushmasligi kerak.
    assert list(sync.scalars(select(AdminAuditLog)).all()) == []
