"""Reklama joylash: narx → payment_pending → to'lov → faol.

Migratsiyagacha reklama kabinet JSON'iga tushardi, public reklamalar esa
relatsion jadvaldan o'qilardi — ya'ni yangi reklama hech qachon bosh
sahifada chiqmasdi.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.advertisements.model import Advertisement
from app.advertisements.pricing import (
    REGION_KEYS,
    AdPricingError,
    calculate_ad_price,
    normalize_ad_region,
)
from app.advertisements.authoring_schemas import (
    AdvertisementCreate,
    AdvertisementQuoteRequest,
    AdvertisementTarget,
)
from app.advertisements.service import AdvertisementAuthoringService
from app.core.errors import ApiError
from app.db.base import Base
from app.payments.model import PlatformPrice


NOW = datetime(2026, 8, 7, 9, 0, tzinfo=UTC)
SHOP = 7
RATE = 20_000


class AsyncStore:
    def __init__(self, sync: Session) -> None:
        self.sync = sync
        self.sequences: dict[str, int] = {}

    def add(self, value):
        self.sync.add(value)

    def get_bind(self):
        return self.sync.get_bind()

    async def get(self, model, key, **kwargs):
        return self.sync.get(model, key)

    async def delete(self, value):
        self.sync.delete(value)

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def flush(self):
        for value in list(self.sync.new):
            if not hasattr(value, "id") or value.id is not None:
                continue
            table = value.__table__.name
            highest = self.sequences.get(table)
            if highest is None:
                highest = int(
                    self.sync.scalar(select(func.max(value.__table__.c.id))) or 0
                )
            highest += 1
            self.sequences[table] = highest
            value.id = highest
        self.sync.flush()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


@pytest.fixture
def advertisement_context():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            PlatformPrice.__table__,
            Advertisement.__table__,
        ),
    )
    with Session(engine, expire_on_commit=False) as seed:
        seed.add_all((
            Account(
                id=SHOP,
                account_type=AccountType.BUSINESS,
                login="choyxona",
                password_hash="hash",
                telegram_user_id=None,
                status="active",
                created_at=NOW,
                updated_at=NOW,
            ),
            PlatformPrice(
                id=1,
                price_code="advertisement_district_hour",
                amount_uzs=RATE,
                service_type="advertisement",
                config={},
                active=1,
                created_at=int(NOW.timestamp()),
                updated_at=int(NOW.timestamp()),
            ),
        ))
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    service = AdvertisementAuthoringService(
        sessions,
        image_url_provider=lambda key: f"https://r2.test/{key}" if key else "",
        now_provider=lambda: NOW,
    )
    try:
        yield service, sessions, engine
    finally:
        engine.dispose()


def _body(**overrides) -> AdvertisementCreate:
    payload = {
        "title": "Choyxona ochildi",
        "caption": "Yangi taomlar",
        "targets": [AdvertisementTarget(
            level="district", region="Toshkent shahri", district="Chilonzor",
        )],
        "duration_days": 7,
        "daily_all_day": True,
        "daily_start": "00:00",
        "daily_end": "00:00",
        "start_date": "2026-08-10",
        "desktop_image_object_key": "public/ads/1.png",
        "mobile_image_object_key": "",
        "crop_x": 50.0,
        "crop_y": 50.0,
        "crop_zoom": 1.0,
        "placement": "home",
    }
    payload.update(overrides)
    return AdvertisementCreate(**payload)


# ------------------------------------------------- Toshkent katalog xatosi


def test_tashkent_city_and_region_are_separate():
    """v1656da ikkalasi bitta kalitga tushib, shahar tumanlari yo'qolgan.

    Oqibati: Toshkent shahridagi tumanga reklama sotib bo'lmasdi va
    viloyat tanlansa narx noto'g'ri chiqardi.
    """
    assert normalize_ad_region("Toshkent shahri") != normalize_ad_region(
        "Toshkent viloyati"
    )
    assert len(REGION_KEYS) == 14


def test_city_district_can_be_targeted():
    quote = calculate_ad_price(
        targets=[{
            "level": "district",
            "region": "Toshkent shahri",
            "district": "Chilonzor",
        }],
        duration_days=1,
        daily_all_day=True,
        daily_start="00:00",
        daily_end="00:00",
        district_hour_rate=RATE,
    )
    assert quote["district_count"] == 1
    assert quote["total"] == 24 * RATE


def test_city_and_region_have_different_district_counts():
    def count(region: str) -> int:
        return calculate_ad_price(
            targets=[{"level": "region", "region": region, "district": ""}],
            duration_days=1,
            daily_all_day=True,
            daily_start="00:00",
            daily_end="00:00",
            district_hour_rate=RATE,
        )["district_count"]

    assert count("Toshkent shahri") == 11
    assert count("Toshkent viloyati") == 14


# ------------------------------------------------------------------- narx


async def test_quote_matches_v1656_formula(advertisement_context):
    """Narx = tumanlar × kunlik soatlar × kunlar × tarif."""
    service, _sessions, _engine = advertisement_context

    quote = await service.quote(AdvertisementQuoteRequest(
        targets=[AdvertisementTarget(
            level="district", region="Toshkent shahri", district="Chilonzor",
        )],
        duration_days=7,
        daily_all_day=False,
        daily_start="09:00",
        daily_end="18:00",
    ))
    assert quote.district_count == 1
    assert quote.hours_per_day == 9
    assert quote.billable_district_hours == 1 * 9 * 7
    assert quote.total == 63 * RATE


async def test_rate_comes_from_the_admin_panel(advertisement_context):
    service, _sessions, engine = advertisement_context
    with Session(engine) as change:
        row = change.scalar(select(PlatformPrice))
        row.amount_uzs = 33_000
        change.commit()

    rates = await service.rates()
    assert rates.district_hour_rate == 33_000
    assert rates.duration_days == [1, 3, 7, 14, 30]


async def test_invalid_duration_is_refused(advertisement_context):
    service, _sessions, _engine = advertisement_context
    with pytest.raises(ApiError) as failure:
        await service.quote(AdvertisementQuoteRequest(
            targets=[AdvertisementTarget(level="republic")],
            duration_days=5,
            daily_all_day=True,
        ))
    assert failure.value.code == "advertisement_price_invalid"


async def test_republic_cannot_be_mixed(advertisement_context):
    service, _sessions, _engine = advertisement_context
    with pytest.raises(ApiError):
        await service.quote(AdvertisementQuoteRequest(
            targets=[
                AdvertisementTarget(level="republic"),
                AdvertisementTarget(level="region", region="Toshkent shahri"),
            ],
            duration_days=1,
            daily_all_day=True,
        ))


# -------------------------------------------------------------- yaratish


async def test_new_advertisement_is_not_visible_until_paid(
    advertisement_context,
):
    service, _sessions, engine = advertisement_context

    created = await service.create(
        account_id=SHOP, account_type=AccountType.BUSINESS, body=_body(),
    )
    assert created.status == "payment_pending"
    assert created.price == 168 * RATE

    with Session(engine) as check:
        row = check.scalar(select(Advertisement))
        # Public ro'yxat faqat `active` ni oladi.
        assert row.status == "payment_pending"
        assert row.migration_run_id is None
        assert row.price_code == "advertisement_district_hour"


async def test_owner_sees_own_advertisements_only(advertisement_context):
    service, _sessions, _engine = advertisement_context
    await service.create(
        account_id=SHOP, account_type=AccountType.BUSINESS, body=_body(),
    )

    mine = await service.list_mine(
        account_id=SHOP, account_type=AccountType.BUSINESS,
    )
    assert len(mine) == 1
    stranger = await service.list_mine(
        account_id=SHOP + 5, account_type=AccountType.BUSINESS,
    )
    assert stranger == []


async def test_stranger_cannot_delete(advertisement_context):
    service, _sessions, _engine = advertisement_context
    created = await service.create(
        account_id=SHOP, account_type=AccountType.BUSINESS, body=_body(),
    )

    with pytest.raises(ApiError) as failure:
        await service.delete(
            account_id=SHOP + 5,
            account_type=AccountType.BUSINESS,
            advertisement_id=created.id,
        )
    assert failure.value.status_code == 404


# ------------------------------------------------------- to'lovdan keyin


async def test_payment_activates_and_shifts_the_schedule(
    advertisement_context,
):
    """Tasdiqlash sanadan keyin bo'lsa, jadval oldinga suriladi."""
    service, sessions, engine = advertisement_context
    created = await service.create(
        account_id=SHOP, account_type=AccountType.BUSINESS, body=_body(),
    )
    # Boshlanish 10-avgust edi; tasdiq 12-avgustda keladi.
    approved = int(datetime(2026, 8, 12, 6, 0, tzinfo=UTC).timestamp())

    async with sessions() as session:
        await service.activate_paid(
            session,
            advertisement_id=created.id,
            account_id=SHOP,
            now=approved,
        )
        await session.commit()

    with Session(engine) as check:
        row = check.scalar(select(Advertisement))
        assert row.status == "active"
        start = row.start_at.replace(tzinfo=UTC)
        assert int(start.timestamp()) >= approved
        # 7 kunlik sutkalik reklama.
        assert row.end_at.replace(tzinfo=UTC) - start == (
            datetime(2026, 1, 8, tzinfo=UTC) - datetime(2026, 1, 1, tzinfo=UTC)
        )


async def test_activation_is_refused_twice(advertisement_context):
    service, sessions, _engine = advertisement_context
    created = await service.create(
        account_id=SHOP, account_type=AccountType.BUSINESS, body=_body(),
    )
    approved = int(NOW.timestamp())

    async with sessions() as session:
        await service.activate_paid(
            session, advertisement_id=created.id,
            account_id=SHOP, now=approved,
        )
        await session.commit()

    async with sessions() as session:
        with pytest.raises(ApiError) as failure:
            await service.activate_paid(
                session, advertisement_id=created.id,
                account_id=SHOP, now=approved,
            )
        assert failure.value.code == "advertisement_not_pending"


async def test_activation_checks_the_owner(advertisement_context):
    """Boshqa akkauntning to'lovi reklamani yoqmaydi."""
    service, sessions, _engine = advertisement_context
    created = await service.create(
        account_id=SHOP, account_type=AccountType.BUSINESS, body=_body(),
    )

    async with sessions() as session:
        with pytest.raises(ApiError) as failure:
            await service.activate_paid(
                session,
                advertisement_id=created.id,
                account_id=SHOP + 5,
                now=int(NOW.timestamp()),
            )
        assert failure.value.code == "advertisement_owner_mismatch"
