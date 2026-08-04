"""Kursga yozilish — relatsion domen testlari.

Ariza avval o'quv markazining profil qatorini qulflab, butun arizalar
ro'yxatini qayta yozardi. Bu testlar yangi yo'lni qo'riqlaydi: bitta
INSERT, bazadagi takroriylik to'sig'i va qabul qilishning atomikligi.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.cabinet_records.model import (
    CabinetRecord,
    CabinetRecordField,
    CabinetResource,
)
from app.catalog.model import CatalogItem
from app.core.errors import ApiError
from app.db.base import Base
from app.education.model import (
    CourseEnrollment,
    EducationGroup,
    EducationStudent,
)
from app.education.repository import EducationEnrollmentRepository
from app.education.schemas import CourseEnrollmentCreate
from app.education.service import EducationEnrollmentService
from app.legacy_migration.model import LegacyIdMap, OwnerState, ReviewState
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile


NOW = datetime(2026, 8, 4, 9, 30, tzinfo=UTC)
STAMP = 1785000000
BUSINESS_ID = 7
USER_ID = 70
LINKED_BUSINESS_ID = 8
COURSE_PUBLIC_ID = "s_english000000000"
LEGACY_COURSE_ID = 51


class AsyncStore:
    """Sinxron SQLite sessiyasi ustidan async interfeys."""

    def __init__(self, sync: Session) -> None:
        self.sync = sync
        self.sequences: dict[str, int] = {}

    def add(self, value):
        self.sync.add(value)

    def get_bind(self):
        return self.sync.get_bind()

    async def get(self, model, key, **kwargs):
        return self.sync.get(model, key)

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
            if table not in self.sequences:
                highest = self.sync.scalar(
                    select(func.max(value.__table__.c.id))
                )
                self.sequences[table] = int(highest or 0)
            self.sequences[table] += 1
            value.id = self.sequences[table]
        self.sync.flush()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


def _account(identifier: int, kind: AccountType) -> Account:
    return Account(
        id=identifier,
        account_type=kind,
        login=f"edu_{kind.value}_{identifier}",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def _business(account_id: int, payload: dict) -> BusinessProfile:
    return BusinessProfile(
        account_id=account_id,
        name="English House",
        phone="+998901112233",
        description="",
        public_username=f"school{account_id}",
        direction="Ta'lim faoliyati",
        activity_type="",
        address="Toshkent",
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
        cabinet_payload=payload,
    )


def _user(account_id: int) -> UserProfile:
    return UserProfile(
        account_id=account_id,
        name="Ali Valiyev",
        phone="+998901234567",
        public_username=f"user{account_id}",
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
    )


def _course(enrollment_status: str = "open") -> CatalogItem:
    return CatalogItem(
        id=900,
        business_account_id=BUSINESS_ID,
        catalog_group_id=None,
        source_record_key=f"item:{LEGACY_COURSE_ID}",
        public_id=COURSE_PUBLIC_ID,
        kind="service",
        name="Ingliz tili",
        price_text="500 000",
        unit="dona",
        note="",
        image_object_key="",
        queue_enabled=False,
        status="active",
        review_state=ReviewState.READY,
        owner_state=OwnerState.LINKED,
        owner_name_snapshot="English House",
        migration_run_id=None,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def education(request):
    enrollment_status = getattr(request, "param", "open")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            UserProfile.__table__,
            BusinessProfile.__table__,
            ProfileLink.__table__,
            CatalogItem.__table__,
            LegacyIdMap.__table__,
            CabinetResource.__table__,
            CabinetRecord.__table__,
            CabinetRecordField.__table__,
            EducationGroup.__table__,
            EducationStudent.__table__,
            CourseEnrollment.__table__,
        ),
    )
    payload = {
        "items": [{
            "id": LEGACY_COURSE_ID,
            "name": "Ingliz tili",
            "kind": "service",
            "enrollment_status": enrollment_status,
        }],
    }
    with Session(engine) as seed:
        seed.add_all((
            _account(BUSINESS_ID, AccountType.BUSINESS),
            _account(USER_ID, AccountType.USER),
            _account(LINKED_BUSINESS_ID, AccountType.BUSINESS),
        ))
        seed.flush()
        seed.add_all((
            _business(BUSINESS_ID, payload),
            _user(USER_ID),
            _course(enrollment_status),
            ProfileLink(
                user_account_id=USER_ID,
                business_account_id=LINKED_BUSINESS_ID,
                created_at=NOW,
            ),
            EducationGroup(
                id=1,
                business_account_id=BUSINESS_ID,
                legacy_source_id=11,
                course_item_id=LEGACY_COURSE_ID,
                name="Kechki guruh",
                teacher_id=None,
                status="active",
                created_at=STAMP,
                updated_at=STAMP,
            ),
        ))
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    service = EducationEnrollmentService(sessions, now=lambda: STAMP)
    try:
        yield service, engine, sessions
    finally:
        engine.dispose()


def _body(note: str = "Kechki guruh qulay") -> CourseEnrollmentCreate:
    return CourseEnrollmentCreate(
        course_item_public_id=COURSE_PUBLIC_ID,
        phone="+998901234567",
        note=note,
    )


async def test_enrollment_is_one_insert_without_touching_the_profile(education):
    """Ariza profil qatorini qulflamasin va ro'yxatni qayta yozmasin."""
    service, engine, _sessions = education
    statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _capture(conn, cursor, statement, *args):
        statements.append(statement)

    created = await service.create(
        account_id=USER_ID,
        account_type=AccountType.USER,
        body=_body(),
    )

    assert created.ok is True
    inserts = [
        text for text in statements
        if text.lstrip().upper().startswith("INSERT INTO COURSE_ENROLLMENTS")
    ]
    assert len(inserts) == 1
    assert not [
        text for text in statements
        if "business_profiles" in text and text.lstrip().upper().startswith("UPDATE")
    ]
    with Session(engine) as check:
        row = check.scalars(select(CourseEnrollment)).one()
        assert row.status == "new"
        assert row.user_account_id == USER_ID
        assert row.course_item_id == LEGACY_COURSE_ID
        assert row.customer_name == "Ali Valiyev"


async def test_duplicate_enrollment_is_blocked_by_the_database(education):
    service, engine, _sessions = education
    await service.create(
        account_id=USER_ID,
        account_type=AccountType.USER,
        body=_body(),
    )

    with pytest.raises(ApiError) as error:
        await service.create(
            account_id=USER_ID,
            account_type=AccountType.USER,
            body=_body("ikkinchi urinish"),
        )

    assert error.value.code == "course_enrollment_duplicate"
    with Session(engine) as check:
        assert check.scalar(select(func.count(CourseEnrollment.id))) == 1


async def test_business_account_enrolls_through_its_linked_profile(education):
    """v1656da kirgan har qanday akkaunt kursga yozila olardi."""
    service, engine, _sessions = education

    created = await service.create(
        account_id=LINKED_BUSINESS_ID,
        account_type=AccountType.BUSINESS,
        body=_body(),
    )

    assert created.ok is True
    with Session(engine) as check:
        row = check.scalars(select(CourseEnrollment)).one()
        assert row.user_account_id == USER_ID


@pytest.mark.parametrize("education", ["closed"], indirect=True)
async def test_closed_course_is_rejected(education):
    service, engine, _sessions = education

    with pytest.raises(ApiError) as error:
        await service.create(
            account_id=USER_ID,
            account_type=AccountType.USER,
            body=_body(),
        )

    assert error.value.code == "course_enrollment_closed"
    with Session(engine) as check:
        assert check.scalar(select(func.count(CourseEnrollment.id))) == 0


async def test_accept_writes_student_and_status_together(education):
    service, engine, sessions = education
    await service.create(
        account_id=USER_ID,
        account_type=AccountType.USER,
        body=_body(),
    )
    with Session(engine) as check:
        enrollment_id = check.scalars(select(CourseEnrollment.id)).one()

    async with sessions() as session:
        await service.accept_in_session(
            session,
            business_account_id=BUSINESS_ID,
            enrollment_id=enrollment_id,
            group_id=1,
            now=STAMP,
        )
        await session.commit()

    with Session(engine) as check:
        enrollment = check.scalars(select(CourseEnrollment)).one()
        student = check.scalars(select(EducationStudent)).one()
        assert enrollment.status == "accepted"
        assert enrollment.group_id == 1
        assert student.group_id == 1
        assert student.user_account_id == USER_ID
        assert student.full_name == "Ali Valiyev"


async def test_accept_leaves_nothing_behind_when_group_is_missing(education):
    """Guruh topilmasa, o'quvchi ham, holat ham o'zgarmasin."""
    service, engine, sessions = education
    await service.create(
        account_id=USER_ID,
        account_type=AccountType.USER,
        body=_body(),
    )
    with Session(engine) as check:
        enrollment_id = check.scalars(select(CourseEnrollment.id)).one()

    async with sessions() as session:
        with pytest.raises(ApiError) as error:
            await service.accept_in_session(
                session,
                business_account_id=BUSINESS_ID,
                enrollment_id=enrollment_id,
                group_id=999,
                now=STAMP,
            )
        await session.rollback()

    assert error.value.code == "education_group_required"
    with Session(engine) as check:
        assert check.scalar(select(func.count(EducationStudent.id))) == 0
        assert check.scalars(select(CourseEnrollment)).one().status == "new"


async def test_rejected_enrollment_frees_the_duplicate_guard(education):
    """Rad etilgandan keyin qayta yozilish mumkin — v1656 kabi."""
    service, engine, sessions = education
    await service.create(
        account_id=USER_ID,
        account_type=AccountType.USER,
        body=_body(),
    )
    with Session(engine) as check:
        enrollment_id = check.scalars(select(CourseEnrollment.id)).one()

    async with sessions() as session:
        await service.reject_in_session(
            session,
            business_account_id=BUSINESS_ID,
            enrollment_id=enrollment_id,
            now=STAMP,
        )
        await session.commit()

    created = await service.create(
        account_id=USER_ID,
        account_type=AccountType.USER,
        body=_body("qayta ariza"),
    )
    assert created.ok is True
    with Session(engine) as check:
        assert check.scalar(select(func.count(CourseEnrollment.id))) == 2


async def test_list_rows_keep_the_v1656_field_names(education):
    """Kabinet ekrani shu nomlarni kutadi — o'zgarsa ekran buziladi."""
    service, engine, sessions = education
    await service.create(
        account_id=USER_ID,
        account_type=AccountType.USER,
        body=_body(),
    )
    repository = EducationEnrollmentRepository()

    async with sessions() as session:
        rows = await repository.list_rows(
            session,
            business_account_id=BUSINESS_ID,
            resource="education_enrollments",
        )
        groups = await repository.list_rows(
            session,
            business_account_id=BUSINESS_ID,
            resource="education_groups",
        )

    assert rows is not None and len(rows) == 1
    assert set(rows[0]) >= {
        "id", "business_id", "course_item_id", "user_id", "user_account_id",
        "user_legacy_id", "customer_name", "phone", "note", "status",
        "created_at", "updated_at",
    }
    assert rows[0]["status"] == "new"
    assert groups is not None
    assert set(groups[0]) >= {
        "id", "course_item_id", "name", "status", "created_at", "updated_at",
    }
