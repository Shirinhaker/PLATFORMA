from datetime import UTC, datetime

import pytest

from app.accounts.model import Account, AccountType
from app.cabinet_records.backfill import backfill_all_profiles
from app.cabinet_records.repository import CabinetRecordRepository
from app.profiles.model import BusinessProfile, UserProfile


@pytest.mark.asyncio
async def test_backfill_all_profiles_is_lossless_and_idempotent(db_session):
    now = datetime(2026, 7, 31, 0, 0, tzinfo=UTC)
    user = Account(
        account_type=AccountType.USER,
        login="v7_normalize_user",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=now,
        updated_at=now,
    )
    business = Account(
        account_type=AccountType.BUSINESS,
        login="v7_normalize_business",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([user, business])
    await db_session.flush()

    user_payload = {
        "orders": [{
            "id": 1,
            "status": "new",
            "items": [{"id": 10, "name": "Non", "qty": 2}],
        }],
        "notifications": [{"id": 2, "is_read": 0}],
        "specialist": {"bio": "Usta", "offers": []},
        "saved": [],
        "legacy_enabled": True,
        "legacy_note": None,
    }
    business_payload = {
        "items": [{"id": 4, "name": "Mahsulot", "price": 15000}],
        "stories": [{
            "id": 5,
            "caption": "Bugungi ish",
            "views": [{"id": 6, "viewer_id": 1}],
            "reports": [],
        }],
        "messages": [],
        "settings": {"show_map": True},
    }
    user_profile = UserProfile(
        account_id=user.id,
        name="V7 User",
        phone="",
        public_username="v7_user",
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
        name="V7 Business",
        phone="",
        description="",
        public_username="v7_business",
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

    first = await backfill_all_profiles(db_session)
    second = await backfill_all_profiles(db_session)

    assert first.profiles_total == 2
    assert first.profiles_verified == 2
    assert first.source_digest == first.target_digest
    assert second.source_digest == first.source_digest
    assert second.target_digest == first.target_digest
    assert second.records_source == first.records_source
    assert second.records_target == first.records_target

    repository = CabinetRecordRepository()
    restored_user = await repository.read_payload(
        db_session,
        account_id=user.id,
        account_type="user",
    )
    restored_business = await repository.read_payload(
        db_session,
        account_id=business.id,
        account_type="business",
    )
    assert restored_user == user_payload
    assert restored_business == business_payload
    assert user_profile.cabinet_payload == user_payload
    assert business_profile.cabinet_payload == business_payload
