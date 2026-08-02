from __future__ import annotations

import importlib.util
import os
from datetime import UTC, date, datetime
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.accounts.model import Account, AccountType
from app.catalog.model import CatalogItem
from app.legacy_migration.model import OwnerState, ReviewState
from app.profiles.model import BusinessProfile
from app.queues.model import QueueProvider, QueueProviderService
from app.queues.repository import QueueRepository


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0013_queue_provider_backfill.py"
)
NOW = datetime(2026, 8, 3, 7, 0, tzinfo=UTC)


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("queue_provider_backfill", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def business_profile(account_id: int) -> BusinessProfile:
    return BusinessProfile(
        account_id=account_id,
        name="Stomatolog",
        phone="+998901234567",
        description="",
        public_username=f"stomatolog_{account_id}",
        direction="Tibbiy xizmatlar",
        activity_type="Stomatologiya",
        address="Qumqo'rg'on",
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
        followers_count=0,
        following_count=0,
        rating_sum=0,
        rating_count=0,
        map_visible=True,
        dashboard_snapshot={},
        recent_activity=[],
        cabinet_payload={
            "staff": [
                {
                    "id": 77,
                    "name": "Real shifokor",
                    "profession": "Stomatolog",
                    "status": "active",
                }
            ],
            "medical_doctors": [
                {
                    "id": 88,
                    "staff_id": 77,
                    "specialty": "Terapevt stomatolog",
                    "experience_years": 9,
                    "qualification": "Oliy toifa",
                    "work_days": "1,2,3,4,5,6",
                    "work_start": "08:00",
                    "work_end": "17:00",
                    "avg_minutes": 15,
                    "room": "3-xona",
                    "bio": "",
                    "status": "active",
                    "mode": "live",
                    "created_at": 1_754_209_200,
                    "updated_at": 1_754_209_200,
                }
            ],
            "medical_doctor_services": [
                {
                    "id": 99,
                    "business_id": account_id,
                    "staff_id": 77,
                    "item_id": 31,
                    "active": 1,
                    "duration_minutes": 15,
                }
            ],
        },
    )


def test_repair_migration_is_after_queue_domain_and_keeps_0012_immutable():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0013_queue_provider_backfill"' in source
    assert 'down_revision = "0012_queue_domain"' in source
    assert "INSERT INTO queue_providers" in source
    assert "INSERT INTO queue_provider_services" in source
    assert "ON CONFLICT (business_account_id, legacy_staff_id) DO NOTHING" in source
    assert "ON CONFLICT (provider_id, catalog_item_id) DO NOTHING" in source


@pytest.mark.asyncio
async def test_repair_backfills_real_v7_provider_and_service_idempotently_on_postgresql():
    migration = load_migration()
    database_url = os.environ.get("KOPRIK_TEST_DATABASE_URL", "")
    if not database_url:
        # CI haqiqiy PostgreSQLda pastdagi tranzaksion oqimni bajaradi. Lokal
        # muhitda esa migration SQL kontrakti baribir majburiy tekshiriladi.
        assert "jsonb_array_elements" in migration.QUEUE_SOURCE_CTES
        assert "medical_doctors" in migration.PROVIDER_BACKFILL_SQL
        assert "medical_doctor_services" in migration.SERVICE_BACKFILL_SQL
        return

    engine = create_async_engine(database_url)
    connection = await engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)
    token = uuid4().hex

    try:
        account = Account(
            account_type=AccountType.BUSINESS,
            login=f"queue-repair-{token}",
            password_hash="hash",
            telegram_user_id=None,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(account)
        await session.flush()
        profile = business_profile(account.id)
        session.add(profile)
        item = CatalogItem(
            business_account_id=account.id,
            source_record_key="31",
            catalog_group_id=None,
            owner_name_snapshot="Stomatolog",
            name="Tish ko'rigi",
            price_text="50 000 so'm",
            unit="dona",
            note="",
            kind="service",
            queue_enabled=True,
            image_object_key="",
            status="active",
            owner_state=OwnerState.LINKED,
            review_state=ReviewState.READY,
            migration_run_id=None,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(item)
        await session.flush()

        assert await session.scalar(
            select(func.count(QueueProvider.id)).where(
                QueueProvider.business_account_id == account.id
            )
        ) == 0

        await session.execute(text(migration.PROVIDER_BACKFILL_SQL))
        await session.execute(text(migration.SERVICE_BACKFILL_SQL))
        await session.flush()

        provider = await session.scalar(
            select(QueueProvider).where(
                QueueProvider.business_account_id == account.id,
                QueueProvider.legacy_staff_id == 77,
            )
        )
        assert provider is not None
        assert (
            provider.staff_name_snapshot,
            provider.profession_snapshot,
            provider.specialty,
            provider.avg_minutes,
            provider.status,
        ) == (
            "Real shifokor",
            "Stomatolog",
            "Terapevt stomatolog",
            15,
            "active",
        )

        repository = QueueRepository()
        options = await repository.provider_options(
            session,
            business_account_id=account.id,
            catalog_item_id=item.id,
            queue_date=date(2026, 8, 3),
        )
        assert [(row.id, queue_count) for row, queue_count in options] == [
            (provider.id, 0)
        ]

        link = await session.scalar(
            select(QueueProviderService).where(
                QueueProviderService.provider_id == provider.id,
                QueueProviderService.catalog_item_id == item.id,
            )
        )
        assert link is not None
        provider.room = "Yangi xona"
        link.duration_minutes = 30
        await session.flush()
        account_id = account.id
        provider_id = provider.id
        link_id = link.id

        # Railway qayta uringan taqdirda yozuv ko'paymaydi va yangi typed API
        # orqali o'zgartirilgan qiymatlar eski snapshot bilan bosib ketilmaydi.
        await session.execute(text(migration.PROVIDER_BACKFILL_SQL))
        await session.execute(text(migration.SERVICE_BACKFILL_SQL))
        await session.flush()
        session.expire_all()

        assert await session.scalar(
            select(func.count(QueueProvider.id)).where(
                QueueProvider.business_account_id == account_id
            )
        ) == 1
        assert await session.scalar(
            select(func.count(QueueProviderService.id)).where(
                QueueProviderService.provider_id == provider_id
            )
        ) == 1
        assert (await session.get(QueueProvider, provider_id)).room == "Yangi xona"
        assert (await session.get(QueueProviderService, link_id)).duration_minutes == 30
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()
        await engine.dispose()
