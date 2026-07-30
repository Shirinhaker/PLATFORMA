from datetime import UTC, datetime

import pytest

from app.accounts.model import Account, AccountType
from app.cabinet_records.repository import CabinetRecordRepository


@pytest.mark.asyncio
async def test_empty_normalized_resource_remains_authoritative(db_session):
    now = datetime(2026, 7, 31, 0, 0, tzinfo=UTC)
    account = Account(
        account_type=AccountType.BUSINESS,
        login="empty_resource_business",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db_session.add(account)
    await db_session.flush()

    repository = CabinetRecordRepository()
    await repository.replace_resource(
        db_session,
        account_id=account.id,
        account_type="business",
        resource="items",
        rows=[],
    )

    assert await repository.has_resource(
        db_session,
        account_id=account.id,
        account_type="business",
        resource="items",
    ) is True
    assert await repository.read_resource(
        db_session,
        account_id=account.id,
        account_type="business",
        resource="items",
    ) == []
    assert await repository.read_payload(
        db_session,
        account_id=account.id,
        account_type="business",
    ) == {"items": []}
