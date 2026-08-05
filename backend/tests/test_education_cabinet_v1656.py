"""Ta'lim kabineti: guruh va o'quvchi boshqaruvi.

Bu bo'limlar ilgari faqat ko'rinardi — yaratish, tahrirlash va
guruhdan guruhga ko'chirish yo'q edi. Testlar v1656 tekshiruvlari
(`api.py:_education_group_payload`, `_education_student_payload`) bilan
mos kelishini qo'riqlaydi.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.cabinet_records.model import (
    CabinetRecord,
    CabinetRecordField,
    CabinetResource,
)
from app.core.errors import ApiError
from app.db.base import Base
from app.education.cabinet_service import EducationCabinetService
from app.education.model import (
    EducationGroup,
    EducationStudent,
    EducationStudentGroupHistory,
)
from app.profiles.model import BusinessProfile


NOW = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)
STAMP = 1785100000
BUSINESS_ID = 7
LEGACY_COURSE_ID = 51


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


def _business() -> BusinessProfile:
    return BusinessProfile(
        account_id=BUSINESS_ID,
        name="English House",
        phone="+998901112233",
        description="",
        public_username="school7",
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
        cabinet_payload={
            "items": [{
                "id": LEGACY_COURSE_ID,
                "name": "Ingliz tili",
                "kind": "service",
            }],
        },
    )


@pytest.fixture
def cabinet():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            BusinessProfile.__table__,
            CabinetResource.__table__,
            CabinetRecord.__table__,
            CabinetRecordField.__table__,
            EducationGroup.__table__,
            EducationStudent.__table__,
            EducationStudentGroupHistory.__table__,
        ),
    )
    with Session(engine) as seed:
        seed.add(Account(
            id=BUSINESS_ID,
            account_type=AccountType.BUSINESS,
            login="edu_business",
            password_hash="hash",
            telegram_user_id=None,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        ))
        seed.flush()
        seed.add(_business())
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    yield EducationCabinetService(), engine, sessions
    engine.dispose()


async def _make_group(service, sessions, **overrides):
    data = {"name": "Kechki guruh", "course_item_id": LEGACY_COURSE_ID}
    data.update(overrides)
    async with sessions() as session:
        profile = await session.get(BusinessProfile, BUSINESS_ID)
        group_id = await service.create_group_in_session(
            session,
            business_account_id=BUSINESS_ID,
            profile=profile,
            data=data,
            now=STAMP,
        )
        await session.commit()
    return group_id


async def test_group_is_created_with_v1656_fields(cabinet):
    service, engine, sessions = cabinet

    group_id = await _make_group(
        service,
        sessions,
        teacher_name="Aziza",
        room_name="2-xona",
        capacity="12",
        weekdays=["mon", "wed", "xxx"],
        lesson_from="18:00",
        lesson_to="19:30",
    )

    with Session(engine) as check:
        group = check.get(EducationGroup, group_id)
        assert group.name == "Kechki guruh"
        assert group.course_item_id == LEGACY_COURSE_ID
        assert group.teacher_name == "Aziza"
        assert group.capacity == 12
        assert group.weekdays == "mon,wed"
        assert group.status == "active"


async def test_group_rejects_empty_name_and_unknown_course(cabinet):
    service, _engine, sessions = cabinet

    async with sessions() as session:
        profile = await session.get(BusinessProfile, BUSINESS_ID)
        with pytest.raises(ApiError) as empty:
            await service.create_group_in_session(
                session,
                business_account_id=BUSINESS_ID,
                profile=profile,
                data={"name": "   "},
                now=STAMP,
            )
        with pytest.raises(ApiError) as unknown:
            await service.create_group_in_session(
                session,
                business_account_id=BUSINESS_ID,
                profile=profile,
                data={"name": "Guruh", "course_item_id": 999},
                now=STAMP,
            )

    assert empty.value.code == "education_group_name_required"
    assert unknown.value.code == "education_course_not_found"


async def test_attendance_billing_requires_package(cabinet):
    """v1656: qatnashuv bo'yicha hisoblashda paket majburiy."""
    service, _engine, sessions = cabinet

    async with sessions() as session:
        profile = await session.get(BusinessProfile, BUSINESS_ID)
        with pytest.raises(ApiError) as error:
            await service.create_group_in_session(
                session,
                business_account_id=BUSINESS_ID,
                profile=profile,
                data={"name": "Guruh", "billing_type": "attendance"},
                now=STAMP,
            )

    assert error.value.code == "education_package_required"


async def test_group_delete_is_soft(cabinet):
    """v1656 kabi: yozuv o'chmaydi, arxivga o'tadi."""
    service, engine, sessions = cabinet
    group_id = await _make_group(service, sessions)

    async with sessions() as session:
        await service.delete_group_in_session(
            session,
            business_account_id=BUSINESS_ID,
            group_id=group_id,
            now=STAMP,
        )
        await session.commit()

    with Session(engine) as check:
        assert check.get(EducationGroup, group_id).status == "deleted"
        assert check.scalar(select(func.count(EducationGroup.id))) == 1


async def test_student_create_opens_group_history(cabinet):
    service, engine, sessions = cabinet
    group_id = await _make_group(service, sessions)

    async with sessions() as session:
        student_id = await service.create_student_in_session(
            session,
            business_account_id=BUSINESS_ID,
            data={
                "full_name": "Ali Valiyev",
                "group_id": group_id,
                "phone": "+998901234567",
                "monthly_fee": "300 000",
                "joined_date": "2026-08-01",
            },
            now=STAMP,
        )
        await session.commit()

    with Session(engine) as check:
        student = check.get(EducationStudent, student_id)
        history = check.scalars(select(EducationStudentGroupHistory)).one()
        assert student.monthly_fee == 300000
        assert student.group_id == group_id
        assert history.group_id == group_id
        assert history.started_date == "2026-08-01"
        assert history.ended_date == ""


async def test_transfer_closes_old_history_and_opens_new(cabinet):
    service, engine, sessions = cabinet
    first = await _make_group(service, sessions)
    second = await _make_group(service, sessions, name="Ertalabki guruh")

    async with sessions() as session:
        student_id = await service.create_student_in_session(
            session,
            business_account_id=BUSINESS_ID,
            data={"full_name": "Ali", "group_id": first},
            now=STAMP,
        )
        await session.commit()

    async with sessions() as session:
        await service.transfer_student_in_session(
            session,
            business_account_id=BUSINESS_ID,
            student_id=student_id,
            group_id=second,
            note="Ertalabki vaqt qulay",
            now=STAMP,
        )
        await session.commit()

    with Session(engine) as check:
        student = check.get(EducationStudent, student_id)
        rows = check.scalars(
            select(EducationStudentGroupHistory).order_by(
                EducationStudentGroupHistory.id
            )
        ).all()
        assert student.group_id == second
        assert len(rows) == 2
        assert rows[0].group_id == first and rows[0].ended_date != ""
        assert rows[1].group_id == second and rows[1].ended_date == ""
        assert rows[1].note == "Ertalabki vaqt qulay"


async def test_transfer_rejects_same_group_and_unknown_group(cabinet):
    service, _engine, sessions = cabinet
    group_id = await _make_group(service, sessions)

    async with sessions() as session:
        student_id = await service.create_student_in_session(
            session,
            business_account_id=BUSINESS_ID,
            data={"full_name": "Ali", "group_id": group_id},
            now=STAMP,
        )
        await session.commit()

    async with sessions() as session:
        with pytest.raises(ApiError) as same:
            await service.transfer_student_in_session(
                session,
                business_account_id=BUSINESS_ID,
                student_id=student_id,
                group_id=group_id,
                note="",
                now=STAMP,
            )
        with pytest.raises(ApiError) as missing:
            await service.transfer_student_in_session(
                session,
                business_account_id=BUSINESS_ID,
                student_id=student_id,
                group_id=999,
                note="",
                now=STAMP,
            )

    assert same.value.code == "education_student_same_group"
    assert missing.value.code == "education_group_required"


async def test_student_delete_is_soft_and_closes_history(cabinet):
    service, engine, sessions = cabinet
    group_id = await _make_group(service, sessions)

    async with sessions() as session:
        student_id = await service.create_student_in_session(
            session,
            business_account_id=BUSINESS_ID,
            data={"full_name": "Ali", "group_id": group_id},
            now=STAMP,
        )
        await session.commit()

    async with sessions() as session:
        await service.delete_student_in_session(
            session,
            business_account_id=BUSINESS_ID,
            student_id=student_id,
            now=STAMP,
        )
        await session.commit()

    with Session(engine) as check:
        assert check.get(EducationStudent, student_id).status == "deleted"
        assert check.scalars(
            select(EducationStudentGroupHistory)
        ).one().ended_date != ""


async def test_student_requires_name_and_existing_group(cabinet):
    service, _engine, sessions = cabinet

    async with sessions() as session:
        with pytest.raises(ApiError) as empty:
            await service.create_student_in_session(
                session,
                business_account_id=BUSINESS_ID,
                data={"full_name": " "},
                now=STAMP,
            )
        with pytest.raises(ApiError) as missing:
            await service.create_student_in_session(
                session,
                business_account_id=BUSINESS_ID,
                data={"full_name": "Ali", "group_id": 999},
                now=STAMP,
            )

    assert empty.value.code == "education_student_name_required"
    assert missing.value.code == "education_group_required"


async def test_group_change_through_update_moves_history(cabinet):
    """Tahrirlashda guruh o'zgarsa ham tarix yangilanadi."""
    service, engine, sessions = cabinet
    first = await _make_group(service, sessions)
    second = await _make_group(service, sessions, name="Ikkinchi")

    async with sessions() as session:
        student_id = await service.create_student_in_session(
            session,
            business_account_id=BUSINESS_ID,
            data={"full_name": "Ali", "group_id": first},
            now=STAMP,
        )
        await session.commit()

    async with sessions() as session:
        await service.update_student_in_session(
            session,
            business_account_id=BUSINESS_ID,
            student_id=student_id,
            data={"group_id": second},
            now=STAMP,
        )
        await session.commit()

    with Session(engine) as check:
        rows = check.scalars(
            select(EducationStudentGroupHistory).order_by(
                EducationStudentGroupHistory.id
            )
        ).all()
        assert [row.group_id for row in rows] == [first, second]
        assert rows[0].ended_date != "" and rows[1].ended_date == ""
