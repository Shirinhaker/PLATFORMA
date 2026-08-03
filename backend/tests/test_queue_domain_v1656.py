import asyncio
import inspect
import os
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.cabinet_records.model import (
    CabinetRecord,
    CabinetRecordField,
    CabinetResource,
)
from app.catalog.model import CatalogGroup, CatalogItem
from app.catalog.repository import list_public_catalog
from app.catalog.schemas import PublicCatalogParams
from app.core.errors import ApiError
from app.db.base import Base
from app.legacy_migration.model import OwnerState, ReviewState
from app.listings.model import Listing, ListingMedia
from app.notifications.model import Notification
from app.orders.model import Order
from app.profiles.model import BusinessProfile, UserProfile
from app.public_discovery.repository import load_public_profile
from app.public_ids import build_content_public_id, build_profile_public_id
from app.queues.model import (
    QueueCounter,
    QueueEntry,
    QueueHistory,
    QueueProvider,
    QueueProviderService,
)
from app.queues.repository import QueueRepository
from app.queues.router import router as queues_router
from app.queues.schemas import (
    QueueCreate,
    QueueOfflineCreate,
    QueueProviderWrite,
    QueueStatusChange,
    QueueSwap,
)
from app.queues.service import QueueService
from app.staff.model import StaffMember


NOW = datetime(2026, 8, 2, 7, 0, tzinfo=UTC)  # O'zbekistonda 12:00


class AsyncStore:
    def __init__(self, session: Session):
        self.sync = session
        self.sequences: dict[str, int] = {}

    def add(self, value):
        self.sync.add(value)

    async def delete(self, value):
        self.sync.delete(value)

    async def flush(self):
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

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def get(self, model, identity, **_kwargs):
        return self.sync.get(model, identity)

    def get_bind(self):
        return self.sync.get_bind()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


def account(identifier: int, kind: AccountType) -> Account:
    return Account(
        id=identifier,
        account_type=kind,
        login=f"{kind.value}_{identifier}",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def business(identifier: int, *, direction: str) -> BusinessProfile:
    return BusinessProfile(
        account_id=identifier,
        name="Shifo markazi" if identifier == 7 else "Savdo do'koni",
        phone="+998907654321",
        description="",
        public_username=f"business_{identifier}",
        direction=direction,
        activity_type="",
        address="Qumqo'rg'on",
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
        map_visible=False,
        dashboard_snapshot={},
        recent_activity=[],
        cabinet_payload={},
    )


@pytest.fixture
def queue_store():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            UserProfile.__table__,
            BusinessProfile.__table__,
            CatalogGroup.__table__,
            CatalogItem.__table__,
            CabinetResource.__table__,
            CabinetRecord.__table__,
            CabinetRecordField.__table__,
            Listing.__table__,
            ListingMedia.__table__,
            Order.__table__,
            Notification.__table__,
            QueueProvider.__table__,
            QueueProviderService.__table__,
            QueueEntry.__table__,
            QueueHistory.__table__,
            QueueCounter.__table__,
            StaffMember.__table__,
        ),
    )
    session = Session(engine, expire_on_commit=False)
    session.add_all((
        account(5, AccountType.USER),
        account(6, AccountType.USER),
        account(7, AccountType.BUSINESS),
        account(8, AccountType.BUSINESS),
        UserProfile(
            account_id=5,
            name="Ali",
            phone="+998901234567",
            public_username="ali",
            region="Surxondaryo viloyati",
            district="Qumqo'rg'on tumani",
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
        UserProfile(
            account_id=6,
            name="Vali",
            phone="+998909999999",
            public_username="vali",
            region="Surxondaryo viloyati",
            district="Qumqo'rg'on tumani",
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
        business(7, direction="Tibbiy xizmatlar"),
        business(8, direction="Savdo"),
        CatalogItem(
            id=11,
            business_account_id=7,
            source_record_key="31",
            catalog_group_id=None,
            owner_name_snapshot="Shifo markazi",
            name="Qabul",
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
        ),
        CatalogItem(
            id=12,
            business_account_id=8,
            source_record_key="32",
            catalog_group_id=None,
            owner_name_snapshot="Savdo do'koni",
            name="Tovar",
            price_text="10 000 so'm",
            unit="dona",
            note="",
            kind="product",
            queue_enabled=False,
            image_object_key="",
            status="active",
            owner_state=OwnerState.LINKED,
            review_state=ReviewState.READY,
            migration_run_id=None,
            created_at=NOW,
            updated_at=NOW,
        ),
        CabinetResource(
            id=101,
            account_id=7,
            account_type="business",
            resource="staff",
            value_kind="list",
            record_count=1,
            digest="",
        ),
        CabinetRecord(
            id=102,
            resource_id=101,
            source_key="11",
            ordinal=0,
            value_kind="object",
        ),
        CabinetRecordField(
            id=103,
            record_id=102,
            path="/id",
            value_type="integer",
            value_integer=11,
        ),
        CabinetRecordField(
            id=104,
            record_id=102,
            path="/name",
            value_type="text",
            value_text="Ali Valiyev",
        ),
        CabinetRecordField(
            id=105,
            record_id=102,
            path="/profession",
            value_type="text",
            value_text="Terapevt",
        ),
        CabinetRecordField(
            id=106,
            record_id=102,
            path="/status",
            value_type="text",
            value_text="active",
        ),
        StaffMember(
            id=11,
            business_account_id=7,
            legacy_source_id=11,
            name="Ali Valiyev",
            profession="Terapevt",
            phone="",
            salary=0,
            hire_date=None,
            status="active",
            note="",
            login=None,
            password_hash=None,
            can_login=False,
            permissions=[],
            schedule={},
            created_at=NOW,
            updated_at=NOW,
            fired_at=None,
        ),
    ))
    session.commit()
    try:
        yield AsyncStore(session)
    finally:
        session.close()
        engine.dispose()


def service_for(store: AsyncStore) -> QueueService:
    @asynccontextmanager
    async def sessions():
        yield store

    return QueueService(sessions, now_provider=lambda: NOW)


def provider_body(*, mode: str = "live") -> QueueProviderWrite:
    return QueueProviderWrite(
        staff_id=11,
        item_public_ids=[build_content_public_id("service", 11)],
        specialty="Terapevt",
        experience_years=5,
        qualification="Oliy toifa",
        work_days="1,2,3,4,5,6,7",
        work_start="08:00",
        work_end="17:00",
        avg_minutes=20,
        room="12",
        bio="",
        status="active",
        mode=mode,
    )


async def create_provider(service: QueueService, *, mode: str = "live"):
    return await service.create_provider(
        business_account_id=7,
        body=provider_body(mode=mode),
    )


def public_body(
    provider_id: int,
    *,
    slot_time: str = "",
    queue_date: date = date(2026, 8, 3),
) -> QueueCreate:
    return QueueCreate(
        business_public_id=build_profile_public_id("business", 7),
        item_public_id=build_content_public_id("service", 11),
        provider_id=provider_id,
        queue_date=queue_date,
        slot_time=slot_time,
        note="Qo'ng'iroq qiling",
    )


@pytest.mark.asyncio
async def test_provider_setup_reads_relational_staff_without_writing_legacy_payload(queue_store):
    service = service_for(queue_store)

    setup = await service.business_setup(business_account_id=7)
    provider = await create_provider(service)

    assert [(row.id, row.name) for row in setup.staff] == [(11, "Ali Valiyev")]
    assert setup.services[0].public_id == build_content_public_id("service", 11)
    assert provider.staff_id == 11
    assert provider.name == "Ali Valiyev"
    assert provider.profession == "Terapevt"
    assert provider.item_public_ids == [build_content_public_id("service", 11)]
    staff_resource = queue_store.sync.get(CabinetResource, 101)
    assert staff_resource.record_count == 1


@pytest.mark.asyncio
async def test_public_profile_exposes_provider_and_active_today_queue_counts(queue_store):
    service = service_for(queue_store)
    provider = await create_provider(service)
    queue_store.sync.add_all([
        QueueEntry(
            id=700 + queue_no,
            business_account_id=7,
            legacy_source_id=None,
            catalog_item_id=11,
            provider_id=provider.id,
            customer_account_id=None,
            patient_name=f"Mijoz {queue_no}",
            phone="+998900000000",
            service_name_snapshot="Qabul",
            provider_name_snapshot=provider.name,
            queue_date=date(2026, 8, 3),
            queue_no=queue_no,
            queue_code=f"QAB-{queue_no:03d}",
            source="offline",
            status=status,
            note="",
            slot_time=None,
            created_at=NOW,
            updated_at=NOW,
        )
        for queue_no, status in enumerate(
            ("waiting", "called", "in_service", "done", "cancelled"),
            start=1,
        )
    ])
    queue_store.sync.commit()
    business_public_id = build_profile_public_id("business", 7)

    profile = await load_public_profile(
        queue_store,
        kind="business",
        public_id=business_public_id,
        image_url_provider=lambda _key: "",
        queue_date=date(2026, 8, 3),
    )
    catalog = await list_public_catalog(
        queue_store,
        PublicCatalogParams(kind="service"),
        lambda _key: "",
    )

    assert profile is not None
    assert profile.items[0].queue_provider_count == 1
    assert profile.items[0].today_queue_count == 3
    assert profile.queue_total == 3
    assert catalog.items[0].queue_provider_count == 1


@pytest.mark.asyncio
async def test_unsupported_direction_and_disabled_service_are_rejected(queue_store):
    service = service_for(queue_store)

    with pytest.raises(ApiError) as direction_error:
        await service.business_setup(business_account_id=8)
    assert direction_error.value.status_code == 403
    assert direction_error.value.message == "Bu yo'nalishda navbat tizimi ishlamaydi."

    with pytest.raises(ApiError) as item_error:
        await service.options(
            business_public_id=build_profile_public_id("business", 8),
            item_public_id=build_content_public_id("product", 12),
            queue_date=date(2026, 8, 3),
        )
    assert item_error.value.message == "Bu yo'nalishda navbat tizimi ishlamaydi."


@pytest.mark.asyncio
async def test_live_queue_uses_atomic_counter_prevents_duplicate_and_projects_wait(queue_store):
    service = service_for(queue_store)
    provider = await create_provider(service)

    first = await service.create_online(
        account_id=5,
        account_type=AccountType.USER,
        body=public_body(provider.id),
    )
    second = await service.create_online(
        account_id=6,
        account_type=AccountType.USER,
        body=public_body(provider.id),
    )

    assert (first.queue_no, first.queue_code) == (1, "QAB-001")
    assert (second.queue_no, second.queue_code) == (2, "QAB-002")
    assert second.ahead_count == 1
    assert second.wait_minutes == 20
    assert queue_store.sync.scalar(select(QueueCounter.last_number)) == 2

    with pytest.raises(ApiError) as duplicate:
        await service.create_online(
            account_id=5,
            account_type=AccountType.USER,
            body=public_body(provider.id),
        )
    assert duplicate.value.status_code == 400
    assert duplicate.value.message == (
        "Bu xizmatga ushbu kunga allaqachon navbatingiz bor."
    )
    assert queue_store.sync.scalar(select(QueueCounter.last_number)) == 2

    notification = queue_store.sync.scalar(select(Notification).where(
        Notification.account_id == 5,
        Notification.event_key == f"medical_queue:{first.id}:booked",
    ))
    assert notification is not None
    assert notification.title == "Navbat olindi"
    assert notification.payload["medical_queue_id"] == first.id

    mine = await service.list_mine(
        account_id=5,
        account_type=AccountType.USER,
    )
    assert mine[0].business_name == "Shifo markazi"
    assert mine[0].business_direction == "Tibbiy xizmatlar"

    marked = await service.mark_notification_read(
        account_id=5,
        account_type=AccountType.USER,
        notification_id=notification.id,
    )
    assert marked.id == notification.id
    assert marked.medical_queue_id == first.id
    assert marked.is_read is True
    queue_store.sync.refresh(notification)
    assert notification.is_read is True

    with pytest.raises(ApiError) as other_user_notification:
        await service.mark_notification_read(
            account_id=6,
            account_type=AccountType.USER,
            notification_id=notification.id,
        )
    assert other_user_notification.value.status_code == 404

    with pytest.raises(ApiError) as business_notification:
        await service.mark_notification_read(
            account_id=7,
            account_type=AccountType.BUSINESS,
            notification_id=notification.id,
        )
    assert business_notification.value.status_code == 403


@pytest.mark.asyncio
async def test_slot_queue_returns_free_times_and_saves_exact_slot(queue_store):
    service = service_for(queue_store)
    provider = await create_provider(service, mode="slot")

    before = await service.slots(
        business_public_id=build_profile_public_id("business", 7),
        item_public_id=build_content_public_id("service", 11),
        provider_id=provider.id,
        queue_date=date(2026, 8, 2),
    )
    assert before.mode == "slot"
    assert before.slots[0] == "12:20"

    created = await service.create_online(
        account_id=5,
        account_type=AccountType.USER,
        body=public_body(
            provider.id,
            slot_time="12:20",
            queue_date=date(2026, 8, 2),
        ),
    )
    assert created.slot_time == "12:20"
    assert created.queue_no == 740
    assert created.queue_code == "QAB-1220"

    after = await service.slots(
        business_public_id=build_profile_public_id("business", 7),
        item_public_id=build_content_public_id("service", 11),
        provider_id=provider.id,
        queue_date=date(2026, 8, 2),
    )
    assert "12:20" not in after.slots

    with pytest.raises(ApiError) as taken:
        await service.create_online(
            account_id=6,
            account_type=AccountType.USER,
            body=public_body(
                provider.id,
                slot_time="12:20",
                queue_date=date(2026, 8, 2),
            ),
        )
    assert taken.value.status_code == 409
    assert taken.value.message == "Bu vaqt band qilindi. Boshqa vaqt tanlang."


@pytest.mark.asyncio
async def test_business_status_swap_customer_cancel_and_idempotent_notifications(queue_store):
    service = service_for(queue_store)
    provider = await create_provider(service)
    first = await service.create_online(
        account_id=5,
        account_type=AccountType.USER,
        body=public_body(provider.id),
    )
    second = await service.create_online(
        account_id=6,
        account_type=AccountType.USER,
        body=public_body(provider.id),
    )

    called = await service.change_status(
        business_account_id=7,
        queue_id=first.id,
        body=QueueStatusChange(status="called"),
    )
    assert called.status == "called"
    assert queue_store.sync.scalar(select(func.count(Notification.id)).where(
        Notification.event_key == f"medical_queue:{first.id}:called"
    )) == 1
    assert queue_store.sync.scalar(select(func.count(Notification.id)).where(
        Notification.event_key == f"medical_queue:{second.id}:soon:1"
    )) == 1

    swapped = await service.swap(
        business_account_id=7,
        queue_id=first.id,
        body=QueueSwap(other_queue_id=second.id),
    )
    assert swapped.queue_no == 2
    mine = await service.list_mine(
        account_id=5,
        account_type=AccountType.USER,
    )
    assert mine[0].queue_code == "QAB-002"

    with pytest.raises(ApiError) as cannot_cancel:
        await service.cancel_mine(
            account_id=6,
            account_type=AccountType.USER,
            queue_id=first.id,
        )
    assert cannot_cancel.value.status_code == 404

    cancelled = await service.cancel_mine(
        account_id=6,
        account_type=AccountType.USER,
        queue_id=second.id,
    )
    assert cancelled.status == "cancelled"
    assert queue_store.sync.scalar(select(func.count(QueueHistory.id))) >= 3


@pytest.mark.asyncio
async def test_two_actor_queue_chain_reaches_business_notification_and_customer(queue_store):
    service = service_for(queue_store)
    provider = await create_provider(service)
    queue_day = date(2026, 8, 3)

    # 1-aktiv: mijoz ommaviy profildagi variantni tanlab navbat oladi.
    options = await service.options(
        business_public_id=build_profile_public_id("business", 7),
        item_public_id=build_content_public_id("service", 11),
        queue_date=queue_day,
    )
    assert [(row.id, row.queue_count) for row in options.providers] == [
        (provider.id, 0),
    ]
    created = await service.create_online(
        account_id=5,
        account_type=AccountType.USER,
        body=public_body(provider.id, queue_date=queue_day),
    )
    assert (created.queue_code, created.status, created.source) == (
        "QAB-001",
        "waiting",
        "online",
    )

    # 2-aktiv: biznes aynan shu navbatni jonli ro'yxatda ko'rib chaqiradi.
    business_rows = await service.list_business(
        business_account_id=7,
        queue_date=queue_day,
    )
    assert [(row.id, row.patient_name, row.status) for row in business_rows] == [
        (created.id, "Ali", "waiting"),
    ]
    called = await service.change_status(
        business_account_id=7,
        queue_id=created.id,
        body=QueueStatusChange(status="called"),
    )
    assert called.status == "called"

    # 1-aktivga qaytish: bildirishnoma shu navbatga bog'langan va o'qiladi.
    called_notification = queue_store.sync.scalar(
        select(Notification).where(
            Notification.account_id == 5,
            Notification.event_key == f"medical_queue:{created.id}:called",
        )
    )
    assert called_notification is not None
    assert called_notification.title == "Navbatingiz keldi"
    assert called_notification.body == (
        "QAB-001 navbat shifokor tomonidan chaqirildi."
    )
    assert called_notification.action_type == "medical_queue_called"
    assert called_notification.payload["medical_queue_id"] == created.id

    mine = await service.list_mine(
        account_id=5,
        account_type=AccountType.USER,
    )
    assert [(row.id, row.status, row.queue_code) for row in mine] == [
        (created.id, "called", "QAB-001"),
    ]
    marked = await service.mark_notification_read(
        account_id=5,
        account_type=AccountType.USER,
        notification_id=called_notification.id,
    )
    assert (marked.medical_queue_id, marked.is_read) == (created.id, True)
    queue_store.sync.refresh(called_notification)
    assert called_notification.is_read is True


@pytest.mark.asyncio
async def test_business_offline_queue_and_indexed_daily_list(queue_store):
    service = service_for(queue_store)
    provider = await create_provider(service)

    created = await service.create_offline(
        business_account_id=7,
        body=QueueOfflineCreate(
            item_public_id=build_content_public_id("service", 11),
            provider_id=provider.id,
            queue_date=date(2026, 8, 3),
            patient_name="Otabek",
            phone="+998900000000",
            note="",
            slot_time="",
        ),
    )
    rows = await service.list_business(
        business_account_id=7,
        queue_date=date(2026, 8, 3),
    )

    assert created.source == "offline"
    assert created.customer_account_id is None
    assert created.patient_name == "Otabek"
    assert [row.id for row in rows] == [created.id]


def test_queue_router_exposes_typed_public_customer_and_business_endpoints():
    routes = {
        (route.path, method)
        for route in queues_router.routes
        for method in (getattr(route, "methods", set()) or set())
    }
    assert {
        ("/api/v1/queues/options", "GET"),
        ("/api/v1/queues/slots", "GET"),
        ("/api/v1/queues", "POST"),
        ("/api/v1/queues/mine", "GET"),
        ("/api/v1/queues/notifications/{notification_id}/read", "POST"),
        ("/api/v1/queues/{queue_id}/cancel", "POST"),
        ("/api/v1/queues/business/setup", "GET"),
        ("/api/v1/queues/business/providers", "GET"),
        ("/api/v1/queues/business/providers", "POST"),
        ("/api/v1/queues/business/providers/{provider_id}", "PUT"),
        ("/api/v1/queues/business/entries", "GET"),
        ("/api/v1/queues/business/entries", "POST"),
        ("/api/v1/queues/business/entries/{queue_id}/status", "PUT"),
        ("/api/v1/queues/business/entries/{queue_id}/swap", "POST"),
    }.issubset(routes)


def test_queue_repository_uses_atomic_upsert_not_max_scan_for_live_numbers():
    source = Path(QueueRepository.__module__.replace(".", "/") + ".py")
    repository_source = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "queues"
        / source.name
    ).read_text(encoding="utf-8")
    lowered = repository_source.casefold()

    assert "on_conflict_do_update" in repository_source
    assert "returning" in repository_source
    assert "sorted(queue_ids)" in repository_source
    assert "max(QueueEntry.queue_no" not in repository_source
    assert "max(queue_no" not in lowered

    service_source = (
        Path(__file__).resolve().parents[1] / "app" / "queues" / "service.py"
    ).read_text(encoding="utf-8")
    assert "except IntegrityError" in service_source
    assert "await session.rollback()" in service_source


@pytest.mark.asyncio
async def test_queue_options_serializes_before_rollback_on_postgresql():
    database_url = os.environ.get("KOPRIK_TEST_DATABASE_URL", "")
    if not database_url:
        source = inspect.getsource(QueueService.options)
        assert source.index("response = QueueOptionsRead(") < source.index(
            "await session.rollback()"
        )
        return

    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    token = uuid4().hex
    business_id: int | None = None
    catalog_item_id: int | None = None
    provider_id: int | None = None

    try:
        async with sessions.begin() as session:
            business_account = Account(
                account_type=AccountType.BUSINESS,
                login=f"queue-options-{token}",
                password_hash="hash",
                telegram_user_id=None,
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
            session.add(business_account)
            await session.flush()
            business_id = business_account.id

            session.add(BusinessProfile(
                account_id=business_id,
                name="Rollback stomatolog",
                phone="+998901234567",
                description="",
                public_username=f"queue_options_{token[:12]}",
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
                map_visible=False,
                dashboard_snapshot={},
                recent_activity=[],
                cabinet_payload={
                    "staff": [{
                        "id": 77,
                        "name": "Real shifokor",
                        "profession": "Stomatolog",
                        "status": "active",
                    }]
                },
            ))

            item = CatalogItem(
                business_account_id=business_id,
                source_record_key=f"queue-options-{token}",
                catalog_group_id=None,
                owner_name_snapshot="Rollback stomatolog",
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
            catalog_item_id = item.id

            provider = QueueProvider(
                business_account_id=business_id,
                legacy_source_id=None,
                legacy_staff_id=77,
                staff_name_snapshot="Real shifokor",
                profession_snapshot="Stomatolog",
                specialty="Terapevt stomatolog",
                experience_years=9,
                qualification="Oliy toifa",
                work_days="1,2,3,4,5,6,7",
                work_start=time(8, 0),
                work_end=time(17, 0),
                avg_minutes=15,
                room="3-xona",
                bio="",
                status="active",
                mode="live",
                created_at=NOW,
                updated_at=NOW,
            )
            session.add(provider)
            await session.flush()
            provider_id = provider.id
            session.add(QueueProviderService(
                provider_id=provider_id,
                catalog_item_id=catalog_item_id,
                active=True,
                duration_minutes=15,
                created_at=NOW,
                updated_at=NOW,
            ))

        options = await QueueService(
            sessions,
            now_provider=lambda: NOW,
        ).options(
            business_public_id=build_profile_public_id(
                "business", business_id
            ),
            item_public_id=build_content_public_id(
                "service", catalog_item_id
            ),
            queue_date=date(2026, 8, 3),
        )

        assert options.business_public_id == build_profile_public_id(
            "business", business_id
        )
        assert [
            (row.id, row.name, row.item_public_ids, row.queue_count)
            for row in options.providers
        ] == [(
            provider_id,
            "Real shifokor",
            [build_content_public_id("service", catalog_item_id)],
            0,
        )]
    finally:
        if business_id is not None:
            async with sessions.begin() as session:
                if provider_id is not None:
                    await session.execute(
                        delete(QueueProviderService).where(
                            QueueProviderService.provider_id == provider_id
                        )
                    )
                    await session.execute(
                        delete(QueueEntry).where(
                            QueueEntry.provider_id == provider_id
                        )
                    )
                    await session.execute(
                        delete(QueueCounter).where(
                            QueueCounter.provider_id == provider_id
                        )
                    )
                    await session.execute(
                        delete(QueueProvider).where(
                            QueueProvider.id == provider_id
                        )
                    )
                if catalog_item_id is not None:
                    await session.execute(
                        delete(CatalogItem).where(
                            CatalogItem.id == catalog_item_id
                        )
                    )
                await session.execute(
                    delete(BusinessProfile).where(
                        BusinessProfile.account_id == business_id
                    )
                )
                await session.execute(
                    delete(Account).where(Account.id == business_id)
                )
        await engine.dispose()


@pytest.mark.asyncio
async def test_queue_lists_serialize_before_rollback_on_postgresql():
    database_url = os.environ.get("KOPRIK_TEST_DATABASE_URL", "")
    if not database_url:
        for method in (QueueService.list_mine, QueueService.list_business):
            source = inspect.getsource(method)
            assert source.index("response = [") < source.index(
                "await session.rollback()"
            )
        return

    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    token = uuid4().hex
    queue_day = date(2026, 8, 3)
    business_id: int | None = None
    customer_id: int | None = None
    catalog_item_id: int | None = None
    provider_id: int | None = None
    entry_id: int | None = None

    try:
        async with sessions.begin() as session:
            business_account = Account(
                account_type=AccountType.BUSINESS,
                login=f"queue-list-business-{token}",
                password_hash="hash",
                telegram_user_id=None,
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
            customer_account = Account(
                account_type=AccountType.USER,
                login=f"queue-list-customer-{token}",
                password_hash="hash",
                telegram_user_id=None,
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
            session.add_all((business_account, customer_account))
            await session.flush()
            business_id = business_account.id
            customer_id = customer_account.id

            session.add(BusinessProfile(
                account_id=business_id,
                name="Ro'yxat stomatolog",
                phone="+998901234567",
                description="",
                public_username=f"queue_list_{token[:12]}",
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
                map_visible=False,
                dashboard_snapshot={},
                recent_activity=[],
                cabinet_payload={},
            ))

            item = CatalogItem(
                business_account_id=business_id,
                source_record_key=f"queue-list-{token}",
                catalog_group_id=None,
                owner_name_snapshot="Ro'yxat stomatolog",
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
            catalog_item_id = item.id

            provider = QueueProvider(
                business_account_id=business_id,
                legacy_source_id=None,
                legacy_staff_id=8_000_000_000 + business_id,
                staff_name_snapshot="Bunyod",
                profession_snapshot="Stomatolog",
                specialty="Terapevt stomatolog",
                experience_years=9,
                qualification="Oliy toifa",
                work_days="1,2,3,4,5,6,7",
                work_start=time(8, 0),
                work_end=time(17, 0),
                avg_minutes=15,
                room="3-xona",
                bio="",
                status="active",
                mode="live",
                created_at=NOW,
                updated_at=NOW,
            )
            session.add(provider)
            await session.flush()
            provider_id = provider.id

            entry = QueueEntry(
                business_account_id=business_id,
                legacy_source_id=None,
                catalog_item_id=catalog_item_id,
                provider_id=provider_id,
                customer_account_id=customer_id,
                patient_name="Ali",
                phone="+998900000000",
                service_name_snapshot="Tish ko'rigi",
                provider_name_snapshot="Bunyod",
                queue_date=queue_day,
                queue_no=1,
                queue_code="STO-001",
                source="online",
                status="waiting",
                note="STAGING E2E 2026-08-03",
                slot_time=None,
                created_at=NOW,
                updated_at=NOW,
            )
            session.add(entry)
            await session.flush()
            entry_id = entry.id

        service = QueueService(sessions, now_provider=lambda: NOW)
        mine = await service.list_mine(
            account_id=customer_id,
            account_type=AccountType.USER,
        )
        business_rows = await service.list_business(
            business_account_id=business_id,
            queue_date=queue_day,
        )

        expected = [(
            entry_id,
            "STO-001",
            "Ro'yxat stomatolog",
            "Tibbiy xizmatlar",
            "Bunyod",
        )]
        assert [
            (
                row.id,
                row.queue_code,
                row.business_name,
                row.business_direction,
                row.provider_name,
            )
            for row in mine
        ] == expected
        assert [
            (
                row.id,
                row.queue_code,
                row.business_name,
                row.business_direction,
                row.provider_name,
            )
            for row in business_rows
        ] == expected
    finally:
        if business_id is not None:
            async with sessions.begin() as session:
                await session.execute(
                    delete(QueueEntry).where(
                        QueueEntry.business_account_id == business_id
                    )
                )
                if provider_id is not None:
                    await session.execute(
                        delete(QueueProvider).where(
                            QueueProvider.id == provider_id
                        )
                    )
                if catalog_item_id is not None:
                    await session.execute(
                        delete(CatalogItem).where(
                            CatalogItem.id == catalog_item_id
                        )
                    )
                await session.execute(
                    delete(BusinessProfile).where(
                        BusinessProfile.account_id == business_id
                    )
                )
                account_ids = [business_id]
                if customer_id is not None:
                    account_ids.append(customer_id)
                await session.execute(
                    delete(Account).where(Account.id.in_(account_ids))
                )
        await engine.dispose()


@pytest.mark.asyncio
async def test_parallel_live_bookings_receive_distinct_numbers_on_postgresql():
    database_url = os.environ.get("KOPRIK_TEST_DATABASE_URL", "")
    if not database_url:
        # Local SQLite parity tests above still cover the complete flow. CI supplies
        # PostgreSQL and exercises the two independent transactions below.
        assert "on_conflict_do_update" in inspect.getsource(
            QueueRepository.allocate_live_number
        )
        return

    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    token = uuid4().hex
    queue_day = date(2026, 8, 4)
    repository = QueueRepository()
    business_id: int | None = None
    catalog_item_id: int | None = None
    provider_id: int | None = None

    try:
        async with sessions.begin() as session:
            business_account = Account(
                account_type=AccountType.BUSINESS,
                login=f"queue-concurrency-{token}",
                password_hash="hash",
                telegram_user_id=None,
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
            session.add(business_account)
            await session.flush()
            business_id = business_account.id

            item = CatalogItem(
                business_account_id=business_id,
                source_record_key=f"queue-concurrency-{token}",
                catalog_group_id=None,
                owner_name_snapshot="Parallel test",
                name="Qabul",
                price_text="",
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
            catalog_item_id = item.id

            provider = QueueProvider(
                business_account_id=business_id,
                legacy_source_id=None,
                legacy_staff_id=9_000_000_000 + business_id,
                staff_name_snapshot="Parallel provider",
                profession_snapshot="Shifokor",
                specialty="",
                experience_years=0,
                qualification="",
                work_days="1,2,3,4,5,6,7",
                work_start=time(8, 0),
                work_end=time(18, 0),
                avg_minutes=20,
                room="",
                bio="",
                status="active",
                mode="live",
                created_at=NOW,
                updated_at=NOW,
            )
            session.add(provider)
            await session.flush()
            provider_id = provider.id

        assert business_id is not None
        assert catalog_item_id is not None
        assert provider_id is not None

        async def book(patient_name: str) -> int:
            async with sessions.begin() as session:
                queue_no = await repository.allocate_live_number(
                    session,
                    business_account_id=business_id,
                    catalog_item_id=catalog_item_id,
                    provider_id=provider_id,
                    queue_date=queue_day,
                    now=NOW,
                )
                await repository.add_entry(
                    session,
                    QueueEntry(
                        business_account_id=business_id,
                        legacy_source_id=None,
                        catalog_item_id=catalog_item_id,
                        provider_id=provider_id,
                        customer_account_id=None,
                        patient_name=patient_name,
                        phone="",
                        service_name_snapshot="Qabul",
                        provider_name_snapshot="Parallel provider",
                        queue_date=queue_day,
                        queue_no=queue_no,
                        queue_code=f"QAB-{queue_no:03d}",
                        source="offline",
                        status="waiting",
                        note="",
                        slot_time=None,
                        created_at=NOW,
                        updated_at=NOW,
                    ),
                )
                return queue_no

        numbers = await asyncio.gather(book("Birinchi"), book("Ikkinchi"))

        assert sorted(numbers) == [1, 2]
        async with sessions() as session:
            stored_numbers = list((await session.scalars(
                select(QueueEntry.queue_no)
                .where(QueueEntry.provider_id == provider_id)
                .order_by(QueueEntry.queue_no)
            )).all())
        assert stored_numbers == [1, 2]
    finally:
        if business_id is not None:
            async with sessions.begin() as session:
                if provider_id is not None:
                    await session.execute(
                        delete(QueueEntry).where(
                            QueueEntry.provider_id == provider_id
                        )
                    )
                    await session.execute(
                        delete(QueueCounter).where(
                            QueueCounter.provider_id == provider_id
                        )
                    )
                    await session.execute(
                        delete(QueueProvider).where(
                            QueueProvider.id == provider_id
                        )
                    )
                if catalog_item_id is not None:
                    await session.execute(
                        delete(CatalogItem).where(CatalogItem.id == catalog_item_id)
                    )
                await session.execute(
                    delete(Account).where(Account.id == business_id)
                )
        await engine.dispose()
