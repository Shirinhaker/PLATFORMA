from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest

from app.accounts.model import Account, AccountType
from app.cabinet_records.batch_runner import execute_backfill_batches
from app.cabinet_records.verify_existing import verify_existing_normalization
from app.profiles.model import BusinessProfile, UserProfile


@pytest.mark.asyncio
async def test_batched_normalization_is_restartable_and_readonly_verify_passes(
    db_session,
):
    now = datetime(2026, 7, 31, 1, 0, tzinfo=UTC)
    user = Account(
        account_type=AccountType.USER,
        login="batch_normalize_user",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=now,
        updated_at=now,
    )
    business = Account(
        account_type=AccountType.BUSINESS,
        login="batch_normalize_business",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([user, business])
    await db_session.flush()

    user_payload = {
        "saved": [],
        "orders": [{"id": 1, "status": "new", "items": []}],
        "specialist": {"bio": "Usta"},
    }
    business_payload = {
        "items": [{"id": 2, "name": "Non", "price": 5000}],
        "messages": [],
    }
    user_profile = UserProfile(
        account_id=user.id,
        name="Batch User",
        phone="",
        public_username="batch_normalize_user",
        region="",
        district="",
        mahalla="",
        location_exact=False,
        avatar_object_key="",
        avatar_x=50,
        avatar_y=50,
        avatar_zoom=1,
        followers_count=0,
        following_count=0,
        has_business=True,
        dashboard_snapshot={},
        recent_activity=[],
        specialist_profile={},
        cabinet_payload=user_payload,
    )
    business_profile = BusinessProfile(
        account_id=business.id,
        name="Batch Business",
        phone="",
        description="",
        public_username="batch_normalize_business",
        direction="Savdo",
        activity_type="Oziq-ovqat do'koni",
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
        cabinet_payload=business_payload,
    )
    db_session.add_all([user_profile, business_profile])
    await db_session.flush()

    @asynccontextmanager
    async def session_factory():
        yield db_session

    first = await execute_backfill_batches(session_factory, batch_size=1)
    second = await execute_backfill_batches(session_factory, batch_size=1)
    verified = await verify_existing_normalization(db_session)

    assert first.status == "verified"
    assert first.profiles_total == 2
    assert first.profiles_verified == 2
    assert first.batches_committed == 2
    assert first.source_digest == first.target_digest
    assert second.source_digest == first.source_digest
    assert second.target_digest == first.target_digest
    assert verified.ok is True
    assert verified.profiles_verified == 2
    assert verified.marker_mismatches == 0
    assert user_profile.cabinet_payload == user_payload
    assert business_profile.cabinet_payload == business_payload
