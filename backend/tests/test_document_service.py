from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.accounts.model import Account, AccountType
from app.core.errors import ApiError
from app.db.base import Base
from app.documents.model import BusinessDocument, DocumentCounterparty
from app.documents.schemas import (
    CounterpartyWrite,
    DocumentRespond,
    DocumentSend,
    DocumentWrite,
)
from app.documents.service_parts import DocumentService
from app.profiles.model import BusinessProfile

NOW = datetime(2026, 8, 10, 14, 30, tzinfo=UTC)


class AsyncStore:
    def __init__(self, sync: Session) -> None:
        self.sync = sync
        self.sequences: dict[str, int] = {}

    def add(self, value):
        self.sync.add(value)

    async def delete(self, value):
        self.sync.delete(value)

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def get(self, model, identifier):
        return self.sync.get(model, identifier)

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

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()


def account(identifier: int) -> Account:
    return Account(
        id=identifier,
        account_type=AccountType.BUSINESS,
        login=f"document_business_{identifier}",
        password_hash="hash",
        telegram_user_id=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def profile(identifier: int, name: str, tax_id: str) -> BusinessProfile:
    return BusinessProfile(
        account_id=identifier,
        name=name,
        public_username=f"document_business_{identifier}",
        tax_id=tax_id,
    )


@pytest.fixture
def document_context():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=(
            Account.__table__,
            BusinessProfile.__table__,
            DocumentCounterparty.__table__,
            BusinessDocument.__table__,
        ),
    )
    with Session(engine) as seed:
        seed.add_all(
            (
                account(1),
                account(2),
                profile(1, "Turon Savdo", "309-111-222"),
                profile(2, "Olma Savdo", "309 333 444"),
            )
        )
        seed.commit()

    @asynccontextmanager
    async def sessions():
        with Session(engine, expire_on_commit=False) as sync:
            yield AsyncStore(sync)

    service = DocumentService(sessions, now_provider=lambda: NOW)
    try:
        yield service, engine
    finally:
        engine.dispose()


async def test_counterparties_are_owner_mutated_and_business_scoped(
    document_context,
):
    service, _engine = document_context
    created = await service.create_counterparty(
        business_account_id=1,
        is_owner=True,
        body=CounterpartyWrite(
            name=" Olma Savdo MChJ ",
            ctype="Mijoz",
            inn="309333444",
        ),
    )

    rows = await service.list_counterparties(
        business_account_id=1,
        permissions=None,
    )
    assert rows.count == 1
    assert rows.counterparties[0].id == created.id
    assert rows.counterparties[0].name == "Olma Savdo MChJ"
    assert (
        await service.list_counterparties(
            business_account_id=2,
            permissions=None,
        )
    ).count == 0

    with pytest.raises(ApiError) as staff_mutation:
        await service.create_counterparty(
            business_account_id=1,
            is_owner=False,
            body=CounterpartyWrite(name="Begona"),
        )
    assert staff_mutation.value.code == "business_owner_required"

    with pytest.raises(ApiError) as staff_read:
        await service.list_counterparties(
            business_account_id=1,
            permissions=("ombor",),
        )
    assert staff_read.value.code == "staff_permission_required"


async def test_send_and_response_update_both_businesses_atomically(
    document_context,
):
    service, engine = document_context
    counterparty = await service.create_counterparty(
        business_account_id=1,
        is_owner=True,
        body=CounterpartyWrite(name="Olma Savdo", inn="309333444"),
    )
    created = await service.create_document(
        business_account_id=1,
        permissions=None,
        body=DocumentWrite(
            direction="chiquvchi",
            doc_type="Shartnoma",
            title="Yetkazib berish",
            number="7",
            doc_date="2026-08-10",
            contractor_id=counterparty.id,
            body="Shartnoma matni",
        ),
    )

    sent = await service.send_document(
        business_account_id=1,
        permissions=None,
        document_id=created.id,
        body=DocumentSend(receiver_inn="309-333-444"),
    )
    assert sent.receiver_name == "Olma Savdo"

    incoming = await service.list_documents(
        business_account_id=2,
        permissions=("documents",),
        direction="kiruvchi",
    )
    assert incoming.count == 1
    assert incoming.documents[0].sender_name == "Turon Savdo"
    assert incoming.documents[0].status == "kutilmoqda"

    response = await service.respond_document(
        business_account_id=2,
        permissions=("documents",),
        document_id=incoming.documents[0].id,
        body=DocumentRespond(action="qabul"),
    )
    assert response.status == "qabul qilindi"

    with Session(engine) as session:
        source = session.get(BusinessDocument, created.id)
        target = session.get(BusinessDocument, incoming.documents[0].id)
        assert source is not None and source.status == "qabul qilindi"
        assert target is not None and target.status == "qabul qilindi"
        assert target.source_document_id == source.id

    with pytest.raises(ApiError) as repeated:
        await service.respond_document(
            business_account_id=2,
            permissions=("documents",),
            document_id=incoming.documents[0].id,
            body=DocumentRespond(action="rad"),
        )
    assert repeated.value.code == "document_already_responded"


async def test_incoming_document_is_read_only_and_send_is_validated(
    document_context,
):
    service, engine = document_context
    with Session(engine) as seed:
        seed.add(
            BusinessDocument(
                id=20,
                business_account_id=1,
                legacy_source_id=20,
                direction="kiruvchi",
                doc_type="Xat",
                title="",
                number="1",
                doc_date="2026-08-10",
                contractor_id=None,
                body="O'zgarmas matn",
                sender_business_id=2,
                sender_name_snapshot="Olma Savdo",
                receiver_tax_id="309111222",
                status="kutilmoqda",
                source_document_id=None,
                responded_at=None,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        seed.commit()

    replacement = DocumentWrite(
        direction="kiruvchi",
        doc_type="Xat",
        number="1",
        doc_date="2026-08-10",
        body="Almashtirilgan matn",
    )
    with pytest.raises(ApiError) as update_error:
        await service.update_document(
            business_account_id=1,
            permissions=None,
            document_id=20,
            body=replacement,
        )
    assert update_error.value.code == "incoming_document_read_only"

    with pytest.raises(ApiError) as delete_error:
        await service.delete_document(
            business_account_id=1,
            permissions=None,
            document_id=20,
        )
    assert delete_error.value.code == "incoming_document_read_only"

    with pytest.raises(ApiError) as invalid_tax_id:
        await service.send_document(
            business_account_id=1,
            permissions=None,
            document_id=20,
            body=DocumentSend(receiver_inn="123"),
        )
    assert invalid_tax_id.value.code == "receiver_tax_id_invalid"
