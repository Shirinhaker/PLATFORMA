from contextlib import asynccontextmanager
from datetime import UTC, date, datetime

import pytest

from app.accounts.model import Account, AccountType
from app.auth.security import verify_password
from app.core.config import Settings
from app.core.errors import ApiError
from app.profiles.model import BusinessProfile
from app.staff.repository import StaffRepository
from app.staff.schemas import (
    StaffAccessWrite,
    StaffAttendanceWrite,
    StaffMemberCreate,
)
from app.staff.service import StaffService


def account(login: str) -> Account:
    now = datetime(2026, 8, 3, 8, 0, tzinfo=UTC)
    return Account(
        account_type=AccountType.BUSINESS,
        login=login,
        password_hash="owner-hash",
        telegram_user_id=None,
        status="active",
        created_at=now,
        updated_at=now,
    )


def profile(account_id: int) -> BusinessProfile:
    return BusinessProfile(
        account_id=account_id,
        name="Turon Savdo",
        phone="",
        description="",
        public_username=f"staff_test_{account_id}",
        direction="Savdo",
        activity_type="Do‘kon",
        address="",
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
async def staff_context(db_session):
    owner = account("b_staff_service_test")
    other = account("b_staff_service_other")
    db_session.add_all([owner, other])
    await db_session.flush()
    db_session.add_all([profile(owner.id), profile(other.id)])
    await db_session.commit()

    @asynccontextmanager
    async def sessions():
        yield db_session

    now = datetime(2026, 8, 3, 20, 30, tzinfo=UTC)
    service = StaffService(
        sessions,
        Settings(environment="test", csrf_secret="staff-test-csrf"),
        now_provider=lambda: now,
    )
    return service, db_session, owner.id, other.id, now


async def test_staff_login_hashes_password_and_firing_revokes_live_session(staff_context):
    service, session, owner_id, _other_id, now = staff_context
    member = await service.create_member(owner_id, StaffMemberCreate(
        name="Ali Valiyev",
        profession="Kassir",
        phone="+998901234567",
        salary=2_500_000,
        hire_date=date(2026, 8, 1),
        note="",
    ))
    updated = await service.set_access(owner_id, member.id, StaffAccessWrite(
        can_login=True,
        login="ali01",
        password="safe-pass-42",
        permissions=["kassa", "debts", "unknown"],
    ))

    stored = await StaffRepository().member(session, staff_id=member.id)
    assert stored is not None
    assert stored.password_hash != "safe-pass-42"
    assert verify_password(stored.password_hash or "", "safe-pass-42")
    assert updated.permissions == ["kassa", "debts"]
    assert not hasattr(updated, "password")

    raw_token, identity = await service.login(
        "b_staff_service_test", "ali01", "safe-pass-42"
    )
    assert identity.actor_type == "staff"
    assert identity.account_id == owner_id
    assert identity.permissions == ["kassa", "debts"]
    assert await service.resolve_session(raw_token, now) is not None

    await service.set_status(owner_id, member.id, "fired")
    assert await service.resolve_session(raw_token, now) is None


async def test_staff_is_owner_scoped_and_attendance_uses_uzbekistan_date(staff_context):
    service, _session, owner_id, other_id, _now = staff_context
    member = await service.create_member(owner_id, StaffMemberCreate(
        name="Vali Karimov",
        profession="Sotuvchi",
    ))

    with pytest.raises(ApiError) as cross_owner:
        await service.set_status(other_id, member.id, "fired")
    assert cross_owner.value.code == "staff_not_found"

    attendance = await service.set_attendance(
        owner_id,
        member.id,
        StaffAttendanceWrite(
            date=date(2026, 8, 4),
            status="keldi",
            time_in="09:00",
            time_out="18:00",
        ),
    )
    row = next(item for item in attendance.staff if item.id == member.id)
    assert row.status == "keldi"
    assert row.month_present == 1
    assert row.month_minutes == 9 * 60
