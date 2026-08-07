"""Ilova ishga tushganda barcha servislar to'g'ri quriladi.

`create_app()` ning o'zi yetarli emas: u faqat routerlarni bog'laydi.
Servislar `lifespan` ichida quriladi va u faqat haqiqiy startda ishlaydi.

Shu sababli K14 da nom to'qnashuvi productionga chiqib ketdi: yangi
`AdvertisementService` eskisini soyalab qo'ygan, natijada public
reklama servisi noto'g'ri sinfdan qurilib, konteyner ko'tarilmagan —
CI esa buni ko'rmagan, chunki hech bir test lifespan'ni ishga
tushirmagan.
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
import pytest

from app.core.config import Settings
from app.main import create_app


EXPECTED_SERVICES = (
    "advertisement_service",
    "advertisement_authoring_service",
    "admin_auth_service",
    "admin_moderation_service",
    "admin_payment_service",
    "admin_reports_service",
    "auth_service",
    "business_online_service",
    "cash_register_service",
    "catalog_service",
    "debt_ledger_service",
    "dining_service",
    "expense_service",
    "follow_service",
    "inventory_service",
    "listing_service",
    "order_service",
    "payment_service",
    "profile_summary_service",
    "public_discovery_service",
    "queue_service",
    "staff_service",
)


def _settings() -> Settings:
    return Settings(
        environment="test",
        telegram_bot_username="koprik_test_bot",
        otp_secret="test-otp-secret",
        csrf_secret="test-csrf-secret",
        outbox_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    )


@asynccontextmanager
async def _started(app):
    """Lifespan'ni tashqi ulanishlarsiz ishga tushiradi."""
    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture
def app(monkeypatch):
    import app.main as main_module

    # Baza va Redis'ga ulanmaymiz — tekshirilayotgani servislarning
    # qurilishi, tarmoq emas.
    @asynccontextmanager
    async def _fake_session():
        yield SimpleNamespace()

    class FakeDatabase:
        def __init__(self, *_args, **_kwargs) -> None:
            self.session = _fake_session

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            return None

    class FakeRedis:
        def __init__(self, *_args, **_kwargs) -> None:
            self.client = SimpleNamespace()

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            return None

    monkeypatch.setattr(main_module, "Database", FakeDatabase)
    monkeypatch.setattr(main_module, "RedisClient", FakeRedis)
    return create_app(_settings())


async def test_startup_builds_every_service(app):
    """Har bir servis quriladi — nom to'qnashuvi darhol ko'rinadi."""
    async with _started(app):
        missing = [
            name for name in EXPECTED_SERVICES
            if not hasattr(app.state, name)
        ]
        assert missing == [], (
            "Bu servislar startda qurilmadi: " + ", ".join(missing)
        )


async def test_public_and_authoring_advertisement_services_differ(app):
    """Ikkalasi alohida sinf — biri ikkinchisini soyalamaydi.

    K14 da aynan shu buzilgan edi.
    """
    async with _started(app):
        public = app.state.advertisement_service
        authoring = app.state.advertisement_authoring_service

        assert type(public) is not type(authoring)
        # Public servis reklama ro'yxatini beradi.
        assert hasattr(public, "list_public")
        # Joylash servisi yaratish va yoqishni biladi.
        assert hasattr(authoring, "create")
        assert hasattr(authoring, "activate_paid")


async def test_payment_service_can_activate_advertisements(app):
    """To'lov servisi joylash servisini olgan bo'lishi shart."""
    async with _started(app):
        payment = app.state.payment_service
        linked = payment.__dict__.get("_advertisements")
        assert linked is app.state.advertisement_authoring_service
